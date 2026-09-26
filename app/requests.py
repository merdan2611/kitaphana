"""Book requests and upvotes (Sprint 07, ADR-0009).

ANONYMITY IS THE FEATURE. A request stores who posted it (requests.user_id) so abuse can be
traced and rate-limited, and an upvote stores who gave it, but neither is ever rendered on a
public page or returned by any endpoint. Every public query below selects the explicit column
list in _PUBLIC and never `requests.*`, so the requester cannot reach a template by accident.
The only readers of requests.user_id are the rate limit, the reader's own "upvoted" flags, and
the admin panel (the admin_* functions at the bottom, used only behind auth.require_admin).

A request's upvote count is always the number of its rows in request_upvotes; it is never stored.
The reader who posts a request is its first upvote.
"""
from __future__ import annotations

import math
import re
import sqlite3
from contextlib import contextmanager
from datetime import timedelta
from typing import Iterator
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from app import config, ratelimit, search
from app.auth import current_user, safe_next
from app.catalogue import valid_book_id
from app.db import get_db, timestamp
from app.templating import templates

router = APIRouter()

PAGE_SIZE = 20
MAX_TITLE = 300
MAX_AUTHOR = 300
MAX_NOTE = 1000
MAX_SUGGESTIONS = 5
# Merged requests redirect to their target; a chain longer than this is a bug, not a request.
MAX_MERGE_HOPS = 20

# The public list's tabs: key -> label. "mine" needs a signed-in reader.
LISTS = {
    "open": "Açyk soraglar",
    "fulfilled": "Tapylanlar",
    "mine": "Goldanlarym",
}

# What a public page may know about a request. Deliberately no user_id (see the module docstring).
# `upvoted` is about the reader looking at the page (:viewer), never about anyone else.
_PUBLIC = (
    "requests.id, requests.title, requests.author, requests.note, requests.status,"
    " requests.merged_into_id, requests.reject_reason, requests.created_at, requests.resolved_at,"
    " (SELECT COUNT(*) FROM request_upvotes WHERE request_upvotes.request_id = requests.id) AS votes,"
    " EXISTS (SELECT 1 FROM request_upvotes WHERE request_upvotes.request_id = requests.id"
    " AND request_upvotes.user_id = :viewer) AS upvoted,"
    " published_books.id AS book_id, published_books.title AS book_title"
)
# A fulfilled request links to its book only while that book is published.
_FROM = " FROM requests LEFT JOIN published_books ON published_books.id = requests.fulfilled_book_id"


class PostingBlocked(Exception):
    message = (
        "Size sorag goşmak gadagan edildi. Kitaplary gözläp we ýükläp, beýleki soraglary bolsa "
        "goldap bilersiňiz."
    )


class RequestLimited(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(retry_after_seconds)
        self.retry_after_seconds = retry_after_seconds

    @property
    def message(self) -> str:
        wait = ratelimit.wait_phrase(self.retry_after_seconds)
        return f"Siz soňky wagtda gaty köp sorag goşduňyz. {wait} soň täzeden synanyşyň."


class InvalidAction(Exception):
    """An admin action that does not apply to this request (e.g. merging a closed one)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@contextmanager
def _write(conn: sqlite3.Connection) -> Iterator[None]:
    """One write transaction, taken with the write lock first, so a check made inside it (the
    rate limit, a request's status) still holds when the write happens."""
    if conn.in_transaction:
        raise RuntimeError("requests._write needs a connection with no open transaction")
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        conn.rollback()
        raise
    else:
        conn.commit()


# --- Reading, for public pages ---------------------------------------------------------------


def _viewer(user: sqlite3.Row | None) -> int | None:
    return user["id"] if user is not None else None


def list_requests(
    conn: sqlite3.Connection, which: str, viewer: int | None, page: int
) -> tuple[list[sqlite3.Row], int, int]:
    """(requests on this page, total, page number actually shown) for one tab of the list."""
    if which == "open":
        where, order, join = "requests.status = 'open'", "votes DESC, requests.created_at DESC, requests.id DESC", ""
    elif which == "fulfilled":
        where, order, join = "requests.status = 'fulfilled'", "requests.resolved_at DESC, requests.id DESC", ""
    elif which == "mine":
        # Merged requests have no upvotes left: theirs moved to the request they were merged into.
        where, order = "requests.status <> 'merged'", "mine.created_at DESC, requests.id DESC"
        join = " JOIN request_upvotes AS mine ON mine.request_id = requests.id AND mine.user_id = :viewer"
    else:
        raise ValueError(which)
    params = {"viewer": viewer}
    total = conn.execute(f"SELECT COUNT(*) FROM requests{join} WHERE {where}", params).fetchone()[0]
    pages = max(1, math.ceil(total / PAGE_SIZE))
    page = min(max(page, 1), pages)
    rows = conn.execute(
        f"SELECT {_PUBLIC}{_FROM}{join} WHERE {where} ORDER BY {order} LIMIT :limit OFFSET :offset",
        {**params, "limit": PAGE_SIZE, "offset": (page - 1) * PAGE_SIZE},
    ).fetchall()
    return rows, total, page


def get_request(conn: sqlite3.Connection, request_id: int, viewer: int | None) -> sqlite3.Row | None:
    return conn.execute(
        f"SELECT {_PUBLIC}{_FROM} WHERE requests.id = :id", {"id": request_id, "viewer": viewer}
    ).fetchone()


def open_counts(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        "SELECT status, COUNT(*) AS n FROM requests WHERE status IN ('open', 'fulfilled') GROUP BY status"
    ).fetchall()
    return {row["status"]: row["n"] for row in rows}


def _match_where(column: str, title: str) -> list[tuple[str, list[str]]]:
    """Two ways to look for `title` in a folded column, strictest first: every word of the
    title, then any one longer word of it (a different spelling of a short title word, or a
    subtitle, would miss the first)."""
    terms = search.query_terms(title)
    if not terms:
        return []
    strict = (" AND ".join(f"{column} LIKE ? ESCAPE '\\'" for _ in terms), [search.like_pattern(t) for t in terms])
    loose_terms = [t for t in terms if len(t) >= 4]
    ways = [strict]
    if loose_terms and len(terms) > 1:
        ways.append((
            " OR ".join(f"{column} LIKE ? ESCAPE '\\'" for _ in loose_terms),
            [search.like_pattern(t) for t in loose_terms],
        ))
    return ways


def _suggest(conn: sqlite3.Connection, sql: str, column: str, title: str) -> list[sqlite3.Row]:
    found: dict[int, sqlite3.Row] = {}
    for where, values in _match_where(column, title):
        if len(found) >= MAX_SUGGESTIONS:
            break
        for row in conn.execute(sql.format(where=where), values).fetchall():
            if len(found) < MAX_SUGGESTIONS:
                found.setdefault(row["id"], row)
    return list(found.values())


def matching_books(conn: sqlite3.Connection, title: str) -> list[sqlite3.Row]:
    """Published books that may be the one being asked for."""
    sql = f"SELECT * FROM published_books WHERE {{where}} ORDER BY id DESC LIMIT {MAX_SUGGESTIONS}"
    return _suggest(conn, sql, "search_text", title)


def similar_requests(conn: sqlite3.Connection, title: str, viewer: int | None) -> list[sqlite3.Row]:
    """Open requests that may be for the same book, to upvote instead of asking twice."""
    # _PUBLIC uses a named parameter, and the LIKE clauses positional ones; SQLite cannot mix
    # them in one statement, so the viewer goes in as a literal integer (it is our own id).
    viewer_sql = str(int(viewer)) if viewer is not None else "NULL"
    columns = _PUBLIC.replace(":viewer", viewer_sql)
    sql = (
        f"SELECT {columns}{_FROM} WHERE requests.status = 'open' AND ({{where}})"
        f" ORDER BY votes DESC, requests.id DESC LIMIT {MAX_SUGGESTIONS}"
    )
    return _suggest(conn, sql, "requests.search_text", title)


# --- Writing ---------------------------------------------------------------------------------


def check_request_limit(conn: sqlite3.Connection, user_id: int) -> None:
    retry_after = 0
    for count, seconds in config.settings.request_limits:
        since = timestamp(-timedelta(seconds=seconds))
        rows = conn.execute(
            "SELECT created_at FROM requests WHERE user_id = ? AND created_at > ? ORDER BY created_at",
            (user_id, since),
        ).fetchall()
        times = [row["created_at"] for row in rows]
        retry_after = max(retry_after, ratelimit.seconds_until_allowed(times, count, seconds))
    if retry_after:
        raise RequestLimited(retry_after)


def post_request(conn: sqlite3.Connection, user_id: int, title: str, author: str, note: str) -> int:
    """Save a request, with its poster as the first upvote. Raises PostingBlocked or
    RequestLimited, having written nothing."""
    with _write(conn):
        # Read inside the transaction: a block set a moment ago must already count.
        blocked = conn.execute("SELECT requests_blocked FROM users WHERE id = ?", (user_id,)).fetchone()
        if blocked is None or blocked["requests_blocked"]:
            raise PostingBlocked()
        check_request_limit(conn, user_id)
        now = timestamp()
        request_id = conn.execute(
            "INSERT INTO requests (user_id, title, author, note, search_text, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, title, author, note, search.book_search_text(title, author), now),
        ).lastrowid
        conn.execute(
            "INSERT INTO request_upvotes (request_id, user_id, created_at) VALUES (?, ?, ?)",
            (request_id, user_id, now),
        )
    return request_id


def upvote(conn: sqlite3.Connection, request_id: int, user_id: int) -> None:
    """Add the reader's upvote to an open request. A second one is a no-op: the primary key
    refuses it, which is what makes one-per-reader true."""
    conn.execute(
        "INSERT OR IGNORE INTO request_upvotes (request_id, user_id, created_at)"
        " SELECT id, ?, ? FROM requests WHERE id = ? AND status = 'open'",
        (user_id, timestamp(), request_id),
    )
    conn.commit()


def remove_upvote(conn: sqlite3.Connection, request_id: int, user_id: int) -> None:
    conn.execute(
        "DELETE FROM request_upvotes WHERE request_id = ? AND user_id = ?"
        " AND request_id IN (SELECT id FROM requests WHERE status = 'open')",
        (request_id, user_id),
    )
    conn.commit()


def merge_target(conn: sqlite3.Connection, request_id: int) -> int:
    """The request a merged one's page should show: follow merged_into_id to its end."""
    current = request_id
    for _ in range(MAX_MERGE_HOPS):
        row = conn.execute("SELECT merged_into_id FROM requests WHERE id = ?", (current,)).fetchone()
        if row is None or row["merged_into_id"] is None:
            return current
        current = row["merged_into_id"]
    raise RuntimeError(f"merge chain from request {request_id} is too long")


# --- Admin only ------------------------------------------------------------------------------
# These return the requester's phone. They are called only from app/admin.py, whose router is
# behind auth.require_admin.

ADMIN_STATUSES = {
    "open": "Açyk",
    "fulfilled": "Tapylan",
    "rejected": "Ret edilen",
    "merged": "Birleşdirilen",
    "all": "Hemmesi",
}

_ADMIN = (
    "requests.*, users.phone AS requester_phone, users.requests_blocked AS requester_blocked,"
    " (SELECT COUNT(*) FROM request_upvotes WHERE request_upvotes.request_id = requests.id) AS votes,"
    " books.title AS book_title, books.is_published AS book_published"
    " FROM requests JOIN users ON users.id = requests.user_id"
    " LEFT JOIN books ON books.id = requests.fulfilled_book_id"
)


def admin_list(conn: sqlite3.Connection, status: str, page: int) -> tuple[list[sqlite3.Row], int, int]:
    where = "" if status == "all" else "WHERE requests.status = ?"
    params = [] if status == "all" else [status]
    total = conn.execute(f"SELECT COUNT(*) FROM requests {where}", params).fetchone()[0]
    pages = max(1, math.ceil(total / PAGE_SIZE))
    page = min(max(page, 1), pages)
    rows = conn.execute(
        f"SELECT {_ADMIN} {where} ORDER BY votes DESC, requests.created_at DESC, requests.id DESC"
        " LIMIT ? OFFSET ?",
        [*params, PAGE_SIZE, (page - 1) * PAGE_SIZE],
    ).fetchall()
    return rows, total, page


def admin_get(conn: sqlite3.Connection, request_id: int) -> sqlite3.Row | None:
    return conn.execute(f"SELECT {_ADMIN} WHERE requests.id = ?", (request_id,)).fetchone()


def admin_top_open(conn: sqlite3.Connection, limit: int = 5) -> list[sqlite3.Row]:
    return conn.execute(
        f"SELECT {_ADMIN} WHERE requests.status = 'open'"
        " ORDER BY votes DESC, requests.created_at DESC, requests.id DESC LIMIT ?",
        (limit,),
    ).fetchall()


def admin_matching_books(conn: sqlite3.Connection, title: str) -> list[sqlite3.Row]:
    """Any book, drafts included: the admin may fulfil with a book before publishing it."""
    sql = f"SELECT * FROM books WHERE {{where}} ORDER BY id DESC LIMIT {MAX_SUGGESTIONS}"
    return _suggest(conn, sql, "search_text", title)


def admin_similar_open(conn: sqlite3.Connection, request_id: int, title: str) -> list[sqlite3.Row]:
    """Other open requests this one might be a duplicate of."""
    sql = (
        f"SELECT {_ADMIN} WHERE requests.status = 'open' AND requests.id <> {int(request_id)}"
        f" AND ({{where}}) ORDER BY votes DESC, requests.id DESC LIMIT {MAX_SUGGESTIONS}"
    )
    return _suggest(conn, sql, "requests.search_text", title)


ADMIN_PICK_LIMIT = 8


def _all_terms(column: str, query: str) -> tuple[str, list[str]] | None:
    """A WHERE clause matching rows whose folded `column` contains every word of `query`."""
    terms = search.query_terms(query)
    if not terms:
        return None
    return (
        " AND ".join(f"{column} LIKE ? ESCAPE '\\'" for _ in terms),
        [search.like_pattern(term) for term in terms],
    )


def admin_book_choices(conn: sqlite3.Connection, title: str, query: str) -> list[sqlite3.Row]:
    """Books to fulfil a request with, drafts included.

    With a search typed: the books matching it. Without: books that look like the request,
    then the newest books, since the one to pick is usually the one just uploaded for it.
    """
    if query.strip():
        match = _all_terms("search_text", query)
        if match is None:
            return []
        return conn.execute(
            f"SELECT * FROM books WHERE {match[0]} ORDER BY id DESC LIMIT {ADMIN_PICK_LIMIT}", match[1]
        ).fetchall()
    chosen = {row["id"]: row for row in admin_matching_books(conn, title)}
    for row in conn.execute(f"SELECT * FROM books ORDER BY id DESC LIMIT {ADMIN_PICK_LIMIT}"):
        if len(chosen) >= ADMIN_PICK_LIMIT:
            break
        chosen.setdefault(row["id"], row)
    return list(chosen.values())


def admin_request_choices(
    conn: sqlite3.Connection, request_id: int, title: str, query: str
) -> list[sqlite3.Row]:
    """Open requests to merge this one into: matching a search if one is typed, otherwise the
    ones that look like it."""
    if not query.strip():
        return admin_similar_open(conn, request_id, title)
    match = _all_terms("requests.search_text", query)
    if match is None:
        return []
    return conn.execute(
        f"SELECT {_ADMIN} WHERE requests.status = 'open' AND requests.id <> ? AND {match[0]}"
        f" ORDER BY votes DESC, requests.id DESC LIMIT {ADMIN_PICK_LIMIT}",
        [request_id, *match[1]],
    ).fetchall()


def requests_by_user_count(conn: sqlite3.Connection, user_id: int) -> int:
    return conn.execute("SELECT COUNT(*) FROM requests WHERE user_id = ?", (user_id,)).fetchone()[0]


def _status_of(conn: sqlite3.Connection, request_id: int) -> str:
    row = conn.execute("SELECT status FROM requests WHERE id = ?", (request_id,)).fetchone()
    if row is None:
        raise InvalidAction("Beýle sorag ýok.")
    return row["status"]


def fulfil(conn: sqlite3.Connection, request_id: int, book_id: int) -> None:
    with _write(conn):
        if _status_of(conn, request_id) != "open":
            raise InvalidAction("Diňe açyk soragy ýapyp bolýar.")
        if conn.execute("SELECT 1 FROM books WHERE id = ?", (book_id,)).fetchone() is None:
            raise InvalidAction(f"{book_id} belgili kitap ýok.")
        conn.execute(
            "UPDATE requests SET status = 'fulfilled', fulfilled_book_id = ?, resolved_at = ?"
            " WHERE id = ?",
            (book_id, timestamp(), request_id),
        )


def reject(conn: sqlite3.Connection, request_id: int, reason: str) -> None:
    with _write(conn):
        if _status_of(conn, request_id) != "open":
            raise InvalidAction("Diňe açyk soragy ret edip bolýar.")
        conn.execute(
            "UPDATE requests SET status = 'rejected', reject_reason = ?, resolved_at = ? WHERE id = ?",
            (reason, timestamp(), request_id),
        )


def merge(conn: sqlite3.Connection, source_id: int, target_id: int) -> None:
    """Fold a duplicate into another open request. Its upvotes move across, and a reader who
    upvoted both still counts once: the primary key ignores the second copy."""
    with _write(conn):
        if source_id == target_id:
            raise InvalidAction("Soragy özüne birleşdirip bolmaýar.")
        if _status_of(conn, source_id) != "open":
            raise InvalidAction("Diňe açyk soragy birleşdirip bolýar.")
        if _status_of(conn, target_id) != "open":
            raise InvalidAction(f"{target_id} belgili sorag açyk däl: diňe açyk soraga birleşdirip bolýar.")
        conn.execute(
            "INSERT OR IGNORE INTO request_upvotes (request_id, user_id, created_at)"
            " SELECT ?, user_id, created_at FROM request_upvotes WHERE request_id = ?",
            (target_id, source_id),
        )
        conn.execute("DELETE FROM request_upvotes WHERE request_id = ?", (source_id,))
        conn.execute(
            "UPDATE requests SET status = 'merged', merged_into_id = ?, resolved_at = ? WHERE id = ?",
            (target_id, timestamp(), source_id),
        )


def reopen(conn: sqlite3.Connection, request_id: int) -> None:
    """Undo a fulfilment or a rejection made by mistake. A merge cannot be undone: its upvotes
    have already been combined with the other request's."""
    with _write(conn):
        if _status_of(conn, request_id) not in ("fulfilled", "rejected"):
            raise InvalidAction("Diňe tapylan ýa-da ret edilen soragy täzeden açyp bolýar.")
        conn.execute(
            "UPDATE requests SET status = 'open', fulfilled_book_id = NULL, reject_reason = NULL,"
            " resolved_at = NULL WHERE id = ?",
            (request_id,),
        )


def set_posting_blocked(conn: sqlite3.Connection, user_id: int, blocked: bool) -> None:
    conn.execute("UPDATE users SET requests_blocked = ? WHERE id = ?", (int(blocked), user_id))
    conn.commit()


# --- Public pages ----------------------------------------------------------------------------


def _request_id_or_404(raw: str) -> int:
    # Same rule as book ids: canonical digits within SQLite's integer range.
    if not valid_book_id(raw):
        raise HTTPException(status_code=404)
    return int(raw)


def _page_number(raw: str) -> int:
    try:
        return max(int(raw), 1)
    except ValueError:
        return 1


def list_url(which: str = "open", page: int = 1) -> str:
    params: dict[str, str | int] = {}
    if which != "open":
        params["list"] = which
    if page > 1:
        params["page"] = page
    return "/requests" + (f"?{urlencode(params)}" if params else "")


def _login_redirect(next_path: str) -> RedirectResponse:
    return RedirectResponse("/login?" + urlencode({"next": next_path}), status_code=303)


@router.get("/requests")
def request_list(
    request: Request,
    list_name: str = Query("open", alias="list"),
    page: str = "1",
    user=Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    if list_name not in LISTS:
        list_name = "open"
    if list_name == "mine" and user is None:
        return _login_redirect("/requests?list=mine")
    rows, total, page_number = list_requests(conn, list_name, _viewer(user), _page_number(page))
    pages = max(1, math.ceil(total / PAGE_SIZE))
    return templates.TemplateResponse(
        request,
        "requests.html",
        {
            "requests": rows,
            "list_name": list_name,
            "lists": LISTS,
            "counts": open_counts(conn),
            "total": total,
            "page": page_number,
            "pages": pages,
            "list_url": list_url,
            "here": list_url(list_name, page_number),
        },
    )


def _form_page(request: Request, status_code: int = 200, **context):
    context.setdefault("values", {"title": "", "author": "", "note": ""})
    context.setdefault("errors", {})
    context.update(max_title=MAX_TITLE, max_author=MAX_AUTHOR, max_note=MAX_NOTE)
    return templates.TemplateResponse(request, "request_new.html", context, status_code=status_code)


def _new_form_url(title: str, author: str) -> str:
    params = {key: value for key, value in (("title", title), ("author", author)) if value}
    return "/requests/new" + (f"?{urlencode(params)}" if params else "")


@router.get("/requests/new")
def request_new(
    request: Request,
    title: str = "",
    author: str = "",
    user=Depends(current_user),
):
    title, author = " ".join(title.split())[:MAX_TITLE], " ".join(author.split())[:MAX_AUTHOR]
    if user is None:
        return _login_redirect(_new_form_url(title, author))
    if user["requests_blocked"]:
        return _form_page(request, 403, blocked=PostingBlocked.message)
    return _form_page(request, values={"title": title, "author": author, "note": ""})


def validate(title: str, author: str, note: str) -> tuple[dict, dict]:
    """(cleaned values, errors by field)."""
    values = {
        "title": " ".join(title.split()),
        "author": " ".join(author.split()),
        # Keep the reader's line breaks in the note, but no more than one blank line in a row.
        "note": re.sub(r"\n{3,}", "\n\n", "\n".join(line.strip() for line in note.strip().splitlines())),
    }
    errors = {}
    if not search.fold(values["title"]):
        errors["title"] = "Kitabyň adyny ýazyň."
    elif len(values["title"]) > MAX_TITLE:
        errors["title"] = f"Ady {MAX_TITLE} harpdan uzyn bolmaly däl."
    if len(values["author"]) > MAX_AUTHOR:
        errors["author"] = f"Awtoryň ady {MAX_AUTHOR} harpdan uzyn bolmaly däl."
    if len(values["note"]) > MAX_NOTE:
        errors["note"] = f"Bellik {MAX_NOTE} harpdan uzyn bolmaly däl."
    return values, errors


@router.post("/requests/new")
def request_post(
    request: Request,
    title: str = Form(""),
    author: str = Form(""),
    note: str = Form(""),
    confirmed: str = Form(""),
    user=Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    if user is None:
        return _login_redirect("/requests/new")
    values, errors = validate(title, author, note)
    if errors:
        return _form_page(request, 400, values=values, errors=errors)
    if user["requests_blocked"]:
        return _form_page(request, 403, values=values, blocked=PostingBlocked.message)

    if confirmed != "1":
        # Many requests are for books the library already has, or that someone already asked
        # for under another spelling: show those first, and post only once the reader confirms.
        books = matching_books(conn, values["title"])
        similar = similar_requests(conn, values["title"], user["id"])
        if books or similar:
            return _form_page(
                request,
                values=values,
                books=books,
                similar=similar,
                confirm=True,
                here=_new_form_url(values["title"], values["author"]),
            )

    try:
        request_id = post_request(conn, user["id"], values["title"], values["author"], values["note"])
    except PostingBlocked as exc:
        return _form_page(request, 403, values=values, blocked=exc.message)
    except RequestLimited as exc:
        return _form_page(request, 429, values=values, limited=exc.message)
    return RedirectResponse(f"/requests/{request_id}?posted=1", status_code=303)


@router.get("/requests/{request_id}")
def request_page(
    request: Request,
    request_id: str,
    posted: str = "",
    user=Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    number = _request_id_or_404(request_id)
    row = get_request(conn, number, _viewer(user))
    if row is None:
        raise HTTPException(status_code=404)
    if row["status"] == "merged":
        return RedirectResponse(f"/requests/{merge_target(conn, number)}", status_code=303)
    return templates.TemplateResponse(
        request,
        "request.html",
        {"req": row, "posted": posted == "1", "here": f"/requests/{number}"},
    )


def _vote(user, conn, request_id: str, next_url: str, add: bool):
    number = _request_id_or_404(request_id)
    if user is None:
        return _login_redirect(f"/requests/{number}")
    if conn.execute("SELECT 1 FROM requests WHERE id = ?", (number,)).fetchone() is None:
        raise HTTPException(status_code=404)
    (upvote if add else remove_upvote)(conn, number, user["id"])
    return RedirectResponse(safe_next(next_url) or f"/requests/{number}", status_code=303)


@router.post("/requests/{request_id}/upvote")
def request_upvote(
    request_id: str,
    next_url: str = Form("", alias="next"),
    user=Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    return _vote(user, conn, request_id, next_url, add=True)


@router.post("/requests/{request_id}/unvote")
def request_unvote(
    request_id: str,
    next_url: str = Form("", alias="next"),
    user=Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    return _vote(user, conn, request_id, next_url, add=False)
