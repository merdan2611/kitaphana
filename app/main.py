"""FastAPI application entry point."""
from __future__ import annotations

import re
import sqlite3
import tempfile
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app import admin, auth, catalogue, downloads, i18n, requests, storage
from app.config import BASE_DIR, settings
from app.db import connect, current_migration_version, get_db
from app.templating import templates

# Starlette spools any upload over 1 MB to tempfile's directory. /tmp is often tmpfs, i.e. RAM,
# so an 80 MB PDF would sit in memory on a 2 GB server; put the spool on the media disk instead.
tempfile.tempdir = str(storage.tmp_dir())

# For every route: the interface language (app/i18n.py), and who is signed in, so every page's
# header and banner know.
app = FastAPI(
    title="Kitaphana",
    dependencies=[Depends(i18n.use_request_language), Depends(auth.current_user)],
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(catalogue.router)
app.include_router(downloads.router)
app.include_router(requests.router)

_COVER_DIR = re.compile(r"[0-9a-f]{2}")
_COVER_FILE = re.compile(r"[0-9a-f]{64}\.jpg")


@app.exception_handler(404)
def not_found(request: Request, exc: Exception):
    """One real page for every 404: an unknown URL, an unknown or unpublished book, or an admin
    page asked for by a non-admin. It deliberately says nothing about which of those it was."""
    i18n.use(i18n.language_for(request))  # an unmatched URL ran no dependencies
    if not hasattr(request.state, "user"):
        # A URL that matched no route never ran the app-wide current_user dependency.
        conn = connect()
        try:
            auth.identify(request, conn)
        finally:
            conn.close()
    return templates.TemplateResponse(request, "404.html", {}, status_code=404)


@app.get("/")
def home(request: Request, conn: sqlite3.Connection = Depends(get_db)):
    return templates.TemplateResponse(request, "index.html", {"books": catalogue.newest_books(conn)})


@app.get("/dil/{code}")
def choose_language(code: str, next_url: str = Query("/", alias="next")):
    """The language switch (ADR-0021): remember the reader's choice for a year and return them
    to the page they were on. A plain link, so it works with no form and no script."""
    target = auth.local_path(next_url) or "/"
    if urlsplit(target).path.startswith(("/logout", "/dil/")):
        target = "/"
    response = RedirectResponse(target, status_code=303)
    if code in i18n.LANGUAGES:
        response.set_cookie(
            i18n.COOKIE_NAME,
            code,
            max_age=i18n.COOKIE_MAX_AGE,
            httponly=True,
            samesite="lax",
            secure=settings.cookie_secure,
        )
    return response


@app.get("/covers/{prefix}/{name}")
def cover(prefix: str, name: str):
    """Small cover JPEGs. Served by the app for now; nginx can alias /covers/ in Sprint 02.

    Both path parts are matched strictly, so no request can reach outside the covers directory.
    Links carry ?v=<updated_at>, which is what makes the year-long cache safe.
    """
    if not (_COVER_DIR.fullmatch(prefix) and _COVER_FILE.fullmatch(name)):
        raise HTTPException(status_code=404)
    path = storage.media_root() / "covers" / prefix / name
    if not path.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=31536000"})


@app.get("/health")
def health(conn: sqlite3.Connection = Depends(get_db)):
    return {
        "status": "ok",
        "migration": current_migration_version(conn),
        "version": settings.app_version,
    }
