"""The admin panel: upload, list, edit, publish and delete books (Sprint 04), grant stars
(Sprint 06), and fulfil, reject and merge book requests (Sprint 07).

Every route here sits behind auth.require_admin at the router level, so a normal reader gets a
404 from all of them — including the POST handlers, not only the pages that link to them.

No handler here declares File or Form parameters. FastAPI parses those before any dependency
runs, which would let a non-admin push 200 MB at the server before being told 404. Handlers
that take a body are `async def` and read it explicitly once the guard has passed — the one
exception to the project's sync-handler rule (app/db.py) — handing blocking work to the thread
pool by hand. Handlers without a body stay plain `def`.
"""
from __future__ import annotations

import math
import re
import sqlite3
from datetime import date
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from app import pdfmeta, requests, stars, storage
from app.auth import require_admin
from app.catalogue import LANGUAGES, MAX_BOOK_ID
from app.db import get_db, timestamp
from app.phone import InvalidPhone, normalize_phone
from app.search import book_search_text
from app.templating import templates

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])

PAGE_SIZE = 20

STATUS_FILTERS = {
    "all": ("Hemmesi", ""),
    "published": ("Neşir edilen", "is_published = 1"),
    "draft": ("Garalama", "is_published = 0"),
}

NOTICES = {
    "uploaded": "Kitap ýüklendi. Ol entek neşir edilmedi: maglumatlaryny barlaň we neşir ediň.",
    "saved": "Üýtgeşmeler ýatda saklandy.",
    "published": "Kitap neşir edildi: indi ony okyjylar görüp bilýär.",
    "unpublished": "Kitap neşirden aýryldy: okyjylar ony indi görmeýär.",
    "cover": "Täze daşlyk goýuldy.",
    "cover-failed": "PDF-iň birinji sahypasyndan daşlyk döredip bolmady.",
    "deleted": "Kitap we onuň faýly pozuldy.",
    "granted": "Ýazgy goşuldy: okyjynyň balansy täzelendi.",
    "fulfilled": "Sorag ýapyldy: ony soranlar kitaby görýär.",
    "rejected": "Sorag ret edildi: sebäbi hemmä görünýär.",
    "merged": "Sorag birleşdirildi: onuň goldawlary beýleki soraga geçdi.",
    "reopened": "Sorag täzeden açyldy.",
    "blocked": "Bu okyjy indi sorag goşup bilmeýär. Hasaby we ýyldyzlary üýtgemedi.",
    "unblocked": "Bu okyjy ýene sorag goşup bilýär.",
}

# One click clears an empty or nonsense request; its reason is shown publicly like any other.
QUICK_REJECT_REASON = "Boş ýa-da manysyz sorag."
MAX_REJECT_REASON = 300

# A grant is added or, for a correction, taken away; either way at most this many at once.
MAX_GRANT = 1000
MAX_GRANT_NOTE = 500


# --- Form handling ---------------------------------------------------------------------------


def parse_book_form(form) -> tuple[dict, dict, dict]:
    """(raw values for re-display, cleaned fields for storage, errors keyed by field)."""
    raw = {
        key: str(form.get(key) or "").strip()
        for key in ("title", "author", "year", "language", "description", "price_stars")
    }
    errors: dict[str, str] = {}
    fields: dict = {
        "title": raw["title"],
        "author": raw["author"],
        "description": raw["description"],
    }

    if len(raw["title"]) > 300:
        errors["title"] = "Ady 300 harpdan uzyn bolmaly däl."
    if len(raw["author"]) > 300:
        errors["author"] = "Awtoryň ady 300 harpdan uzyn bolmaly däl."
    if len(raw["description"]) > 5000:
        errors["description"] = "Düşündiriş 5000 harpdan uzyn bolmaly däl."

    fields["year"] = None
    if raw["year"]:
        try:
            year = int(raw["year"])
        except ValueError:
            year = None
        if year is None or not 1 <= year <= date.today().year + 1:
            errors["year"] = f"Ýyl 1 bilen {date.today().year + 1} aralygynda san bolmaly."
        else:
            fields["year"] = year

    fields["language"] = raw["language"] or "tk"
    if fields["language"] not in LANGUAGES:
        errors["language"] = "Sanawdaky dilleriň birini saýlaň."

    fields["price_stars"] = 0
    if raw["price_stars"]:
        try:
            price = int(raw["price_stars"])
        except ValueError:
            price = -1
        if not 0 <= price <= 1000:
            errors["price_stars"] = "Baha 0 bilen 1000 ýyldyz aralygynda bolmaly."
        else:
            fields["price_stars"] = price

    return raw, fields, errors


def _book_or_404(conn: sqlite3.Connection, book_id: int) -> sqlite3.Row:
    if not 1 <= book_id <= MAX_BOOK_ID:
        raise HTTPException(status_code=404)  # beyond SQLite's integers: no such book
    book = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    if book is None:
        raise HTTPException(status_code=404)
    return book


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


def _form_values(book: sqlite3.Row) -> dict:
    return {
        "title": book["title"],
        "author": book["author"],
        "year": "" if book["year"] is None else str(book["year"]),
        "language": book["language"],
        "description": book["description"] or "",
        "price_stars": str(book["price_stars"]),
    }


# --- Index and list --------------------------------------------------------------------------


@router.get("")
def admin_index(request: Request, conn: sqlite3.Connection = Depends(get_db)):
    counts = conn.execute(
        "SELECT COUNT(*) AS total, COALESCE(SUM(is_published), 0) AS published FROM books"
    ).fetchone()
    recent = conn.execute("SELECT * FROM books ORDER BY id DESC LIMIT 5").fetchall()
    return templates.TemplateResponse(
        request,
        "admin/index.html",
        {
            "total": counts["total"],
            "published": counts["published"],
            "drafts": counts["total"] - counts["published"],
            "recent": recent,
            "top_requests": requests.admin_top_open(conn),
            "section": "index",
        },
    )


def _like(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


@router.get("/books")
def admin_books(
    request: Request,
    q: str = "",
    status: str = "all",
    page: int = 1,
    notice: str = "",
    conn: sqlite3.Connection = Depends(get_db),
):
    q = q.strip()
    if status not in STATUS_FILTERS:
        status = "all"
    clauses, params = [], []
    if STATUS_FILTERS[status][1]:
        clauses.append(STATUS_FILTERS[status][1])
    if q:
        # LIKE is case-insensitive for ASCII only. Good enough for one admin; the public search
        # in Sprint 05 gets a proper answer.
        clauses.append("(title LIKE ? ESCAPE '\\' OR author LIKE ? ESCAPE '\\')")
        params += [_like(q), _like(q)]
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    total = conn.execute(f"SELECT COUNT(*) FROM books {where}", params).fetchone()[0]
    pages = max(1, math.ceil(total / PAGE_SIZE))
    page = min(max(page, 1), pages)
    books = conn.execute(
        f"SELECT * FROM books {where} ORDER BY id DESC LIMIT ? OFFSET ?",
        [*params, PAGE_SIZE, (page - 1) * PAGE_SIZE],
    ).fetchall()
    return templates.TemplateResponse(
        request,
        "admin/books.html",
        {
            "books": books,
            "q": q,
            "status": status,
            "status_filters": STATUS_FILTERS,
            "page": page,
            "pages": pages,
            "total": total,
            "notice": NOTICES.get(notice),
            "languages": LANGUAGES,
            "section": "books",
        },
    )


# --- Upload ----------------------------------------------------------------------------------


def _new_page(request: Request, status_code: int = 200, **context):
    context.setdefault("values", {"language": "tk", "price_stars": "0"})
    context.setdefault("errors", {})
    context.update(languages=LANGUAGES, section="new")
    return templates.TemplateResponse(
        request, "admin/book_new.html", context, status_code=status_code
    )


@router.get("/books/new")
def admin_book_new(request: Request):
    return _new_page(request)


def _ingest_upload(request: Request, conn: sqlite3.Connection, form):
    raw, fields, errors = parse_book_form(form)
    upload = form.get("pdf")
    if not isinstance(upload, UploadFile) or not upload.filename:
        errors["pdf"] = "PDF faýly saýlaň."
    if errors:
        return _new_page(request, 400, values=raw, errors=errors)
    try:
        staged = storage.stage(upload.file)
        book_id = storage.ingest(conn, staged, original_filename=upload.filename, **fields)
    except storage.Duplicate as exc:
        return _new_page(request, 409, values=raw, duplicate=exc.existing)
    except storage.IngestError as exc:
        return _new_page(request, 400, values=raw, errors={"pdf": exc.message})
    return _redirect(f"/admin/books/{book_id}?notice=uploaded")


@router.post("/books")
async def admin_book_upload(request: Request, conn: sqlite3.Connection = Depends(get_db)):
    form = await request.form(max_files=1, max_fields=20)
    try:
        return await run_in_threadpool(_ingest_upload, request, conn, form)
    finally:
        await form.close()


# --- Edit, publish, cover --------------------------------------------------------------------


def _edit_page(
    request: Request, conn: sqlite3.Connection, book: sqlite3.Row, status_code: int = 200, **context
):
    context.setdefault("values", _form_values(book))
    context.setdefault("errors", {})
    info = pdfmeta.read_info(storage.media_root() / storage.pdf_relpath(book["content_hash"]))
    context.update(book=book, languages=LANGUAGES, embedded=info, section="books")
    return templates.TemplateResponse(
        request, "admin/book_edit.html", context, status_code=status_code
    )


@router.get("/books/{book_id}")
def admin_book_edit(
    request: Request, book_id: int, notice: str = "", conn: sqlite3.Connection = Depends(get_db)
):
    book = _book_or_404(conn, book_id)
    return _edit_page(request, conn, book, notice=NOTICES.get(notice))


def _save_book(request: Request, conn: sqlite3.Connection, book_id: int, form):
    book = _book_or_404(conn, book_id)
    raw, fields, errors = parse_book_form(form)
    if not fields["title"]:
        errors["title"] = "Kitabyň adyny giriziň."
    if errors:
        return _edit_page(request, conn, book, 400, values=raw, errors=errors)
    conn.execute(
        "UPDATE books SET title = ?, author = ?, year = ?, language = ?, description = ?,"
        " price_stars = ?, updated_at = ?, search_text = ? WHERE id = ?",
        (
            fields["title"], fields["author"], fields["year"], fields["language"],
            fields["description"], fields["price_stars"], timestamp(),
            book_search_text(fields["title"], fields["author"]), book_id,
        ),
    )
    conn.commit()
    return _redirect(f"/admin/books/{book_id}?notice=saved")


@router.post("/books/{book_id}")
async def admin_book_save(
    request: Request, book_id: int, conn: sqlite3.Connection = Depends(get_db)
):
    form = await request.form(max_files=0, max_fields=20)
    try:
        return await run_in_threadpool(_save_book, request, conn, book_id, form)
    finally:
        await form.close()


def _set_published(conn: sqlite3.Connection, book_id: int, published: bool) -> RedirectResponse:
    _book_or_404(conn, book_id)
    conn.execute(
        "UPDATE books SET is_published = ?, updated_at = ? WHERE id = ?",
        (int(published), timestamp(), book_id),
    )
    conn.commit()
    return _redirect(f"/admin/books/{book_id}?notice={'published' if published else 'unpublished'}")


@router.post("/books/{book_id}/publish")
def admin_book_publish(book_id: int, conn: sqlite3.Connection = Depends(get_db)):
    return _set_published(conn, book_id, True)


@router.post("/books/{book_id}/unpublish")
def admin_book_unpublish(book_id: int, conn: sqlite3.Connection = Depends(get_db)):
    return _set_published(conn, book_id, False)


def _store_cover(request: Request, conn: sqlite3.Connection, book_id: int, form):
    book = _book_or_404(conn, book_id)
    upload = form.get("cover")
    if not isinstance(upload, UploadFile) or not upload.filename:
        return _edit_page(request, conn, book, 400, cover_error="Surat faýlyny saýlaň.")
    try:
        storage.store_uploaded_cover(conn, book_id, upload.file)
    except storage.IngestError as exc:
        return _edit_page(request, conn, book, 400, cover_error=exc.message)
    return _redirect(f"/admin/books/{book_id}?notice=cover")


@router.post("/books/{book_id}/cover")
async def admin_book_cover(
    request: Request, book_id: int, conn: sqlite3.Connection = Depends(get_db)
):
    form = await request.form(max_files=1, max_fields=2)
    try:
        return await run_in_threadpool(_store_cover, request, conn, book_id, form)
    finally:
        await form.close()


@router.post("/books/{book_id}/cover/render")
def admin_book_cover_render(book_id: int, conn: sqlite3.Connection = Depends(get_db)):
    _book_or_404(conn, book_id)
    ok = storage.rerender_cover(conn, book_id)
    return _redirect(f"/admin/books/{book_id}?notice={'cover' if ok else 'cover-failed'}")


# --- Delete ----------------------------------------------------------------------------------


@router.get("/books/{book_id}/delete")
def admin_book_delete_confirm(
    request: Request, book_id: int, conn: sqlite3.Connection = Depends(get_db)
):
    book = _book_or_404(conn, book_id)
    return templates.TemplateResponse(
        request, "admin/book_delete.html", {"book": book, "section": "books"}
    )


@router.post("/books/{book_id}/delete")
def admin_book_delete(book_id: int, conn: sqlite3.Connection = Depends(get_db)):
    _book_or_404(conn, book_id)
    storage.delete_book(conn, book_id)
    return _redirect("/admin/books?notice=deleted")


# --- Stars -----------------------------------------------------------------------------------


def _reader_by_phone(conn: sqlite3.Connection, raw_phone: str) -> tuple[sqlite3.Row | None, str | None]:
    """(the account for a phone number as typed, None) or (None, why it could not be found)."""
    try:
        phone = normalize_phone(raw_phone)
    except InvalidPhone as exc:
        return None, exc.message
    reader = conn.execute("SELECT * FROM users WHERE phone = ?", (phone,)).fetchone()
    if reader is None:
        return None, "Bu belgi bilen hasap ýok. Okyjy ilki bir gezek saýta girmeli."
    return reader, None


def _stars_page(
    request: Request, conn: sqlite3.Connection, status_code: int = 200, reader=None, **context
):
    context.setdefault("values", {})
    context.setdefault("errors", {})
    if reader is not None:
        context.update(
            reader=reader,
            reader_balance=stars.balance(conn, reader["id"]),
            reader_entries=stars.history(conn, reader["id"]),
        )
    context.update(recent=stars.recent_entries(conn), section="stars")
    return templates.TemplateResponse(request, "admin/grant.html", context, status_code=status_code)


@router.get("/stars")
def admin_stars(
    request: Request, phone: str = "", notice: str = "", conn: sqlite3.Connection = Depends(get_db)
):
    """Look a reader up by phone to see their balance and history, and grant them stars."""
    reader, error = _reader_by_phone(conn, phone) if phone.strip() else (None, None)
    return _stars_page(
        request,
        conn,
        reader=reader,
        values={"phone": reader["phone"] if reader else ""},
        lookup_phone=phone,
        lookup_error=error,
        notice=NOTICES.get(notice),
    )


def _grant(request: Request, conn: sqlite3.Connection, form):
    values = {key: str(form.get(key) or "").strip() for key in ("phone", "amount", "note")}
    errors: dict[str, str] = {}

    reader, error = _reader_by_phone(conn, values["phone"])
    if error:
        errors["phone"] = error

    # Strictly ASCII digits: int() would also take "1_000" or Arabic-Indic digits.
    amount = int(values["amount"]) if re.fullmatch(r"[+-]?[0-9]{1,7}", values["amount"]) else 0
    if amount == 0 or abs(amount) > MAX_GRANT:
        errors["amount"] = (
            f"1 bilen {MAX_GRANT} aralygynda san giriziň. Ýyldyz aýyrmak üçin minus goýuň: -3."
        )

    if not values["note"]:
        errors["note"] = "Näme üçin berilýändigini ýazyň: bu ýazgy hemişe saklanýar."
    elif len(values["note"]) > MAX_GRANT_NOTE:
        errors["note"] = f"Bellik {MAX_GRANT_NOTE} harpdan uzyn bolmaly däl."

    if not errors:
        try:
            stars.grant(conn, reader["id"], amount, values["note"])
        except stars.InsufficientStars as exc:
            errors["amount"] = (
                f"Okyjynyň balansy {exc.balance} ýyldyz: ondan köp aýryp bolmaýar."
            )
    if errors:
        return _stars_page(request, conn, 400, reader=reader, values=values, errors=errors)
    return _redirect(f"/admin/stars?{urlencode({'phone': reader['phone'], 'notice': 'granted'})}")


@router.post("/stars")
async def admin_grant(request: Request, conn: sqlite3.Connection = Depends(get_db)):
    form = await request.form(max_files=0, max_fields=10)
    try:
        return await run_in_threadpool(_grant, request, conn, form)
    finally:
        await form.close()


# --- Requests --------------------------------------------------------------------------------


@router.get("/requests")
def admin_requests(
    request: Request,
    status: str = "open",
    page: int = 1,
    notice: str = "",
    conn: sqlite3.Connection = Depends(get_db),
):
    if status not in requests.ADMIN_STATUSES:
        status = "open"
    rows, total, page = requests.admin_list(conn, status, page)
    return templates.TemplateResponse(
        request,
        "admin/requests.html",
        {
            "requests": rows,
            "status": status,
            "statuses": requests.ADMIN_STATUSES,
            "total": total,
            "page": page,
            "pages": max(1, math.ceil(total / requests.PAGE_SIZE)),
            "notice": NOTICES.get(notice),
            "section": "requests",
        },
    )


def _request_or_404(conn: sqlite3.Connection, request_id: int) -> sqlite3.Row:
    if not 1 <= request_id <= MAX_BOOK_ID:
        raise HTTPException(status_code=404)
    row = requests.admin_get(conn, request_id)
    if row is None:
        raise HTTPException(status_code=404)
    return row


def _request_page(
    request: Request,
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    status_code: int = 200,
    book_q: str = "",
    req_q: str = "",
    **context,
):
    is_open = row["status"] == "open"
    book_q, req_q = " ".join(book_q.split())[:100], " ".join(req_q.split())[:100]
    context.update(
        req=row,
        book_q=book_q,
        req_q=req_q,
        books=requests.admin_book_choices(conn, row["title"], book_q) if is_open else [],
        similar=requests.admin_request_choices(conn, row["id"], row["title"], req_q) if is_open else [],
        requester_total=requests.requests_by_user_count(conn, row["user_id"]),
        quick_reject=QUICK_REJECT_REASON,
        max_reject_reason=MAX_REJECT_REASON,
        section="requests",
    )
    return templates.TemplateResponse(
        request, "admin/request.html", context, status_code=status_code
    )


@router.get("/requests/{request_id}")
def admin_request(
    request: Request,
    request_id: int,
    notice: str = "",
    book_q: str = "",
    req_q: str = "",
    conn: sqlite3.Connection = Depends(get_db),
):
    row = _request_or_404(conn, request_id)
    return _request_page(request, conn, row, book_q=book_q, req_q=req_q, notice=NOTICES.get(notice))


def _positive_id(raw) -> int | None:
    raw = str(raw or "").strip().lstrip("#")
    return int(raw) if re.fullmatch(r"[1-9][0-9]{0,17}", raw) else None


def _request_action(request: Request, conn: sqlite3.Connection, request_id: int, form, action: str):
    row = _request_or_404(conn, request_id)
    try:
        if action == "fulfil":
            book_id = _positive_id(form.get("book_id"))
            if book_id is None:
                raise requests.InvalidAction("Sanawdan kitap saýlaň.")
            requests.fulfil(conn, request_id, book_id)
            notice = "fulfilled"
        elif action == "reject":
            reason = " ".join(str(form.get("reason") or "").split())
            if not reason:
                raise requests.InvalidAction("Sebäbini ýazyň: ol hemmä görünýär.")
            if len(reason) > MAX_REJECT_REASON:
                raise requests.InvalidAction(f"Sebäbi {MAX_REJECT_REASON} harpdan uzyn bolmaly däl.")
            requests.reject(conn, request_id, reason)
            notice = "rejected"
        elif action == "merge":
            target_id = _positive_id(form.get("target_id"))
            if target_id is None:
                raise requests.InvalidAction("Sanawdan birleşdiriljek soragy saýlaň.")
            requests.merge(conn, request_id, target_id)
            return _redirect(f"/admin/requests/{target_id}?notice=merged")
        else:
            raise HTTPException(status_code=404)
    except requests.InvalidAction as exc:
        return _request_page(request, conn, row, 400, action_error=exc.message)
    return _redirect(f"/admin/requests/{request_id}?notice={notice}")


async def _request_form_action(request: Request, conn, request_id: int, action: str):
    form = await request.form(max_files=0, max_fields=5)
    try:
        return await run_in_threadpool(_request_action, request, conn, request_id, form, action)
    finally:
        await form.close()


@router.post("/requests/{request_id}/fulfil")
async def admin_request_fulfil(
    request: Request, request_id: int, conn: sqlite3.Connection = Depends(get_db)
):
    return await _request_form_action(request, conn, request_id, "fulfil")


@router.post("/requests/{request_id}/reject")
async def admin_request_reject(
    request: Request, request_id: int, conn: sqlite3.Connection = Depends(get_db)
):
    return await _request_form_action(request, conn, request_id, "reject")


@router.post("/requests/{request_id}/merge")
async def admin_request_merge(
    request: Request, request_id: int, conn: sqlite3.Connection = Depends(get_db)
):
    return await _request_form_action(request, conn, request_id, "merge")


@router.post("/requests/{request_id}/reopen")
def admin_request_reopen(
    request: Request, request_id: int, conn: sqlite3.Connection = Depends(get_db)
):
    row = _request_or_404(conn, request_id)
    try:
        requests.reopen(conn, request_id)
    except requests.InvalidAction as exc:
        return _request_page(request, conn, row, 400, action_error=exc.message)
    return _redirect(f"/admin/requests/{request_id}?notice=reopened")


def _set_blocked(conn: sqlite3.Connection, request_id: int, blocked: bool) -> RedirectResponse:
    row = _request_or_404(conn, request_id)
    requests.set_posting_blocked(conn, row["user_id"], blocked)
    return _redirect(f"/admin/requests/{request_id}?notice={'blocked' if blocked else 'unblocked'}")


@router.post("/requests/{request_id}/block")
def admin_request_block(request_id: int, conn: sqlite3.Connection = Depends(get_db)):
    """Stop the reader who posted this request from posting more. Their account, stars and
    upvotes are untouched."""
    return _set_blocked(conn, request_id, True)


@router.post("/requests/{request_id}/unblock")
def admin_request_unblock(request_id: int, conn: sqlite3.Connection = Depends(get_db)):
    return _set_blocked(conn, request_id, False)
