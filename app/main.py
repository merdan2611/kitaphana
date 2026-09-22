"""FastAPI application entry point."""
from __future__ import annotations

import re
import sqlite3
import tempfile

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import admin, auth, catalogue, sessions, storage
from app.config import BASE_DIR, settings
from app.db import connect, current_migration_version, get_db
from app.templating import templates

# Starlette spools any upload over 1 MB to tempfile's directory. /tmp is often tmpfs, i.e. RAM,
# so an 80 MB PDF would sit in memory on a 2 GB server; put the spool on the media disk instead.
tempfile.tempdir = str(storage.tmp_dir())

# current_user runs for every route so every page's header and banner know who is signed in.
app = FastAPI(title="Kitaphana", dependencies=[Depends(auth.current_user)])

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(catalogue.router)

_COVER_DIR = re.compile(r"[0-9a-f]{2}")
_COVER_FILE = re.compile(r"[0-9a-f]{64}\.jpg")


@app.exception_handler(404)
def not_found(request: Request, exc: Exception):
    """One real page for every 404: an unknown URL, an unknown or unpublished book, or an admin
    page asked for by a non-admin. It deliberately says nothing about which of those it was."""
    if not hasattr(request.state, "user"):
        # A URL that matched no route never ran the app-wide current_user dependency.
        conn = connect()
        try:
            request.state.user = sessions.user_for_cookie(
                conn, request.cookies.get(sessions.COOKIE_NAME)
            )
        finally:
            conn.close()
    return templates.TemplateResponse(request, "404.html", {}, status_code=404)


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(request, "index.html")


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
