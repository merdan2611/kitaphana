"""The public catalogue (Sprint 05): browsing, search and book pages.

Every query here reads the published_books view, never the books table, so an unpublished book
cannot appear through a query that forgot the filter (migration 003). Query parameters arrive
in shareable URLs and are parsed leniently: anything unrecognised falls back to its default
rather than producing an error page.
"""
from __future__ import annotations

import math
import re
import sqlite3
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request

from app import search, stars
from app.db import get_db
from app.templating import templates

router = APIRouter()

PAGE_SIZE = 20

# Also the admin form's choices (app/admin.py).
LANGUAGES = {"tk": "Türkmençe", "ru": "Rusça", "en": "Iňlisçe"}

# Sort key -> (link label, ORDER BY). Both are fixed strings, never built from the request.
# Title order uses the folded text, so Ä files with A and capitals with lower case.
SORTS = {
    "new": ("Täze goşulanlar", "created_at DESC, id DESC"),
    "title": ("Ady boýunça", "search_text, id"),
}
DEFAULT_SORT = "new"

# A book id in a URL: canonical digits only (no sign, no leading zero), within SQLite's 64-bit
# integer range, so that nothing a visitor types can reach the database as anything else.
_BOOK_ID = re.compile(r"[1-9][0-9]{0,18}")
MAX_BOOK_ID = 2**63 - 1


def _page_number(raw: str) -> int:
    try:
        page = int(raw)
    except ValueError:
        return 1
    return max(page, 1)


def catalogue_url(q: str = "", lang: str = "", sort: str = DEFAULT_SORT, page: int = 1) -> str:
    """A catalogue URL carrying only the parameters that differ from the defaults."""
    params: dict[str, str | int] = {}
    if q:
        params["q"] = q
    if lang:
        params["lang"] = lang
    if sort != DEFAULT_SORT:
        params["sort"] = sort
    if page > 1:
        params["page"] = page
    return "/books" + (f"?{urlencode(params)}" if params else "")


@router.get("/books")
def catalogue(
    request: Request,
    q: str = "",
    lang: str = "",
    sort: str = DEFAULT_SORT,
    page: str = "1",
    conn: sqlite3.Connection = Depends(get_db),
):
    q = " ".join(q.split())[: search.MAX_QUERY_LENGTH]
    if lang not in LANGUAGES:
        lang = ""
    if sort not in SORTS:
        sort = DEFAULT_SORT

    # A book matches a search when its folded text contains every folded word of the query.
    terms = search.query_terms(q)
    match = ["search_text LIKE ? ESCAPE '\\'" for _ in terms]
    params: list[str | int] = [search.like_pattern(term) for term in terms]
    if q and not terms:
        match.append("0")  # only punctuation was typed; nothing can match it
    match_sql = " AND ".join(match) or "1"

    # Per-language counts for the current search, ignoring the language filter itself, so each
    # language link says how many results choosing it would show.
    counts = {
        row["language"]: row["n"]
        for row in conn.execute(
            f"SELECT language, COUNT(*) AS n FROM published_books WHERE {match_sql} GROUP BY language",
            params,
        )
    }

    where_sql = match_sql + (" AND language = ?" if lang else "")
    where_params = [*params, lang] if lang else params
    total = conn.execute(
        f"SELECT COUNT(*) FROM published_books WHERE {where_sql}", where_params
    ).fetchone()[0]
    pages = max(1, math.ceil(total / PAGE_SIZE))
    page_number = min(_page_number(page), pages)
    books = conn.execute(
        f"SELECT * FROM published_books WHERE {where_sql} ORDER BY {SORTS[sort][1]} LIMIT ? OFFSET ?",
        [*where_params, PAGE_SIZE, (page_number - 1) * PAGE_SIZE],
    ).fetchall()
    catalogue_empty = (
        total == 0 and conn.execute("SELECT COUNT(*) FROM published_books").fetchone()[0] == 0
    )

    def link(**changes) -> str:
        current = {"q": q, "lang": lang, "sort": sort, "page": page_number}
        current.update(changes)
        return catalogue_url(**current)

    return templates.TemplateResponse(
        request,
        "catalogue.html",
        {
            "books": books,
            "q": q,
            "lang": lang,
            "sort": sort,
            "page": page_number,
            "pages": pages,
            "total": total,
            "counts": counts,
            "all_count": sum(counts.values()),
            "languages": LANGUAGES,
            "sorts": SORTS,
            "catalogue_empty": catalogue_empty,
            "link": link,
        },
    )


def published_book_or_404(conn: sqlite3.Connection, book_id: str) -> sqlite3.Row:
    """The published book with this id as it appears in a URL, or a 404.

    Unknown, unpublished and malformed ids all look exactly the same from outside.
    """
    if not valid_book_id(book_id):
        raise HTTPException(status_code=404)
    book = conn.execute("SELECT * FROM published_books WHERE id = ?", (int(book_id),)).fetchone()
    if book is None:
        raise HTTPException(status_code=404)
    return book


def valid_book_id(book_id: str) -> bool:
    """Canonical digits within SQLite's integer range: nothing else reaches the database."""
    return bool(_BOOK_ID.fullmatch(book_id)) and int(book_id) <= MAX_BOOK_ID


def login_url_for(book_id: int) -> str:
    """Sign in, then come back to this book's page."""
    return "/login?" + urlencode({"next": f"/books/{book_id}"})


def book_page_response(
    request: Request,
    conn: sqlite3.Connection,
    book: sqlite3.Row,
    status_code: int = 200,
    download_error: str | None = None,
):
    """The book page. Also rendered by app/downloads.py when a download is refused there."""
    user = getattr(request.state, "user", None)
    return templates.TemplateResponse(
        request,
        "book.html",
        {
            "book": book,
            "language_name": LANGUAGES.get(book["language"], book["language"]),
            "login_url": login_url_for(book["id"]),
            # A book paid for once downloads again for free (app/downloads.py).
            "paid_for": user is not None and stars.has_paid_for(conn, user["id"], book["id"]),
            "download_error": download_error,
        },
        status_code=status_code,
    )


@router.get("/books/{book_id}")
def book_page(request: Request, book_id: str, conn: sqlite3.Connection = Depends(get_db)):
    book = published_book_or_404(conn, book_id)
    return book_page_response(request, conn, book)
