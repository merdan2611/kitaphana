"""Downloads (Sprint 06, ADR-0007, ADR-0014).

A download is two requests:

1. `POST /books/{id}/download` decides and records. It checks the session, the book and the
   rate limit, and appends the `spend` row, all inside one ledger transaction, then redirects
   to step 2. POST, because it can spend stars: a GET could be triggered by a link prefetcher or
   by another site, and the session cookie is SameSite=Lax, so no other site can POST with it.
2. `GET /books/{id}/file` only sends the file, to a reader whose download is already recorded.
   It never writes anything, so when a browser resumes an interrupted download it asks this URL
   again and is neither charged nor counted against the rate limit.

A book paid for once downloads again for free, and each re-download still writes a zero-star
spend row. A refund for the book cancels that: the next download is paid again.

With DOWNLOADS_VIA_NGINX on (production), step 2 returns an empty response carrying
X-Accel-Redirect and nginx sends the bytes, so the worker is free in milliseconds. Off
(development under a bare uvicorn), the app streams the file itself.
"""
from __future__ import annotations

import logging
import re
import sqlite3
import unicodedata
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, Response

from app import config, ratelimit, stars, storage
from app.auth import current_user
from app.catalogue import book_page_response, login_url_for, published_book_or_404, valid_book_id
from app.db import get_db, timestamp
from app.templating import templates

log = logging.getLogger(__name__)

router = APIRouter()

# The nginx location that maps onto MEDIA_DIR. It MUST match the site configuration (Sprint 02):
#     location /_protected/ { internal; alias <MEDIA_DIR>/; }
# `internal` means nginx serves it only in answer to an X-Accel-Redirect from the app, so a
# reader who guesses a path gets a 404. If downloads 404 after a deployment, check this first.
ACCEL_PREFIX = "/_protected/"

MAX_FILENAME_CHARS = 150
# Characters Windows or the header's quoting do not allow in a file name. Control and invisible
# formatting characters (Unicode category C, which includes the right-to-left overrides that can
# make a name display as something else) are dropped separately, in download_filename.
_NOT_IN_FILENAME = re.compile(r'[\\/:*?"<>|]')


class DownloadLimited(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(retry_after_seconds)
        self.retry_after_seconds = retry_after_seconds

    @property
    def message(self) -> str:
        wait = ratelimit.wait_phrase(self.retry_after_seconds)
        return f"Siz soňky wagtda gaty köp kitap ýüklediňiz. {wait} soň täzeden synanyşyň."


# --- Recording a download --------------------------------------------------------------------


def check_download_limit(conn: sqlite3.Connection, user_id: int) -> None:
    """Raise DownloadLimited if one more download would pass any of the configured limits."""
    retry_after = 0
    for count, seconds in config.settings.download_limits:
        times = stars.download_times(conn, user_id, timestamp(-timedelta(seconds=seconds)))
        retry_after = max(retry_after, ratelimit.seconds_until_allowed(times, count, seconds))
    if retry_after:
        raise DownloadLimited(retry_after)


def record_download(conn: sqlite3.Connection, user_id: int, book: sqlite3.Row) -> int:
    """Append the spend row for one download and return how many stars it cost.

    The rate limit, the paid-before check, the balance check and the insert all run in one
    ledger transaction: two downloads at the same moment can neither both be let through on
    stars only one of them has, nor both be charged for a book that only needs paying once.
    Raises DownloadLimited or stars.InsufficientStars, having written nothing.
    """
    with stars.transaction(conn):
        check_download_limit(conn, user_id)
        price = book["price_stars"]
        if price and not stars.has_paid_for(conn, user_id, book["id"]):
            cost = price
        else:
            cost = 0
        stars.append_entry(
            conn,
            user_id,
            -cost,
            "spend",
            reference=stars.book_reference(book["id"]),
            note=book["title"],
        )
    return cost


def may_fetch(conn: sqlite3.Connection, user_id: int, book: sqlite3.Row) -> bool:
    """Whether step 2 may send this book: it is paid for, or it is free and its download has
    been recorded. A free book that later gets a price has to be paid for."""
    if stars.has_paid_for(conn, user_id, book["id"]):
        return True
    return book["price_stars"] == 0 and stars.has_downloaded(conn, user_id, book["id"])


# --- The file --------------------------------------------------------------------------------


def download_filename(title: str, book_id: int) -> str:
    """A file name a reader recognises, "Görogly.pdf", rather than the content hash."""
    cleaned = "".join(
        " " if ch.isspace() or _NOT_IN_FILENAME.match(ch) else ch
        for ch in title or ""
        if ch.isspace() or not unicodedata.category(ch).startswith("C")
    )
    name = " ".join(cleaned.split())[:MAX_FILENAME_CHARS]
    if name.lower().endswith(".pdf"):
        name = name[:-4]
    name = name.strip(". ")
    return f"{name or f'kitap-{book_id}'}.pdf"


def content_disposition(filename: str, book_id: int) -> str:
    """An attachment header with the real name in UTF-8 (RFC 6266), plus a plain-ASCII
    fallback for old clients: "Älem.pdf" falls back to "Alem.pdf"."""
    stem = filename[:-4]
    ascii_stem = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode()
    ascii_stem = " ".join(ascii_stem.split()).strip(". ")
    if not re.search(r"[A-Za-z0-9]", ascii_stem):
        ascii_stem = f"kitap-{book_id}"  # e.g. a Cyrillic title has no ASCII letters left
    return f"attachment; filename=\"{ascii_stem}.pdf\"; filename*=UTF-8''{quote(filename, safe='')}"


def _pdf_path(book: sqlite3.Row) -> tuple[str, Path]:
    relpath = storage.pdf_relpath(book["content_hash"])
    return relpath, storage.media_root() / relpath


def _file_on_disk_or_404(book: sqlite3.Row) -> None:
    """A book whose file is missing must not be charged for. It should never happen; if it
    does, the log says which book, and the reader sees the ordinary 404 page."""
    relpath, path = _pdf_path(book)
    if not path.is_file():
        log.error("Book %s is published but its file is missing: %s", book["id"], relpath)
        raise HTTPException(status_code=404)


# --- Routes ----------------------------------------------------------------------------------


@router.post("/books/{book_id}/download")
def download(
    request: Request,
    book_id: str,
    user=Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    if not valid_book_id(book_id):
        raise HTTPException(status_code=404)
    if user is None:
        return RedirectResponse(login_url_for(int(book_id)), status_code=303)
    book = published_book_or_404(conn, book_id)
    _file_on_disk_or_404(book)

    try:
        cost = record_download(conn, user["id"], book)
    except stars.InsufficientStars as exc:
        return templates.TemplateResponse(
            request,
            "insufficient_stars.html",
            {"book": book, "balance": exc.balance, "missing": exc.needed - exc.balance},
            status_code=402,
        )
    except DownloadLimited as exc:
        return book_page_response(request, conn, book, status_code=429, download_error=exc.message)

    log.info("Download: user %s, book %s, %s stars", user["id"], book["id"], cost)
    return RedirectResponse(f"/books/{book['id']}/file", status_code=303)


@router.get("/books/{book_id}/file")
def download_file(
    book_id: str,
    user=Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    if not valid_book_id(book_id):
        raise HTTPException(status_code=404)
    if user is None:
        return RedirectResponse(login_url_for(int(book_id)), status_code=303)
    book = published_book_or_404(conn, book_id)
    if not may_fetch(conn, user["id"], book):
        # Not recorded yet (or a free book that now has a price): the book page's button
        # records it first.
        return RedirectResponse(f"/books/{book['id']}", status_code=303)
    _file_on_disk_or_404(book)

    relpath, path = _pdf_path(book)
    headers = {
        "Content-Disposition": content_disposition(download_filename(book["title"], book["id"]), book["id"]),
        # The reader's own copy: no shared cache should keep it.
        "Cache-Control": "private",
        "X-Content-Type-Options": "nosniff",
    }
    if config.settings.downloads_via_nginx:
        headers["X-Accel-Redirect"] = ACCEL_PREFIX + relpath
        return Response(status_code=200, media_type="application/pdf", headers=headers)
    # Development only: the worker is busy for the whole transfer (ADR-0014).
    return FileResponse(path, media_type="application/pdf", headers=headers)
