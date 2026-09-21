"""FastAPI application entry point."""
from __future__ import annotations

import sqlite3

from fastapi import Depends, FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import BASE_DIR, settings
from app.db import current_migration_version, get_db

app = FastAPI(title="Kitaphana")

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {"dev_otp_mode": settings.dev_otp_mode},
    )


@app.get("/health")
def health(conn: sqlite3.Connection = Depends(get_db)):
    return {
        "status": "ok",
        "migration": current_migration_version(conn),
        "version": settings.app_version,
    }
