"""FastAPI application entry point."""
from __future__ import annotations

import sqlite3

from fastapi import Depends, FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app import auth
from app.config import BASE_DIR, settings
from app.db import current_migration_version, get_db
from app.templating import templates

# current_user runs for every route so every page's header and banner know who is signed in.
app = FastAPI(title="Kitaphana", dependencies=[Depends(auth.current_user)])

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

app.include_router(auth.router)


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/health")
def health(conn: sqlite3.Connection = Depends(get_db)):
    return {
        "status": "ok",
        "migration": current_migration_version(conn),
        "version": settings.app_version,
    }
