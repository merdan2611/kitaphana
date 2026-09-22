"""The admin panel (Sprint 04): upload, list, edit, publish and delete books.

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
import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from app import pdfmeta, storage
from app.auth import require_admin
from app.db import get_db, timestamp
from app.templating import templates

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])

PAGE_SIZE = 20

LANGUAGES = {"tk": "Türkmençe", "ru": "Rusça", "en": "Iňlisçe"}

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
}


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
        " price_stars = ?, updated_at = ? WHERE id = ?",
        (
            fields["title"], fields["author"], fields["year"], fields["language"],
            fields["description"], fields["price_stars"], timestamp(), book_id,
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
