"""The one Jinja2Templates instance, with the values every page needs.

`dev_otp_mode`, `current_user` and `star_balance` come from a context processor rather than each
handler, so no page can forget the dev-mode banner (ADR-0013) or the signed-in header.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app import config
from app.config import BASE_DIR
from app.phone import format_phone


def _page_globals(request: Request) -> dict:
    return {
        "dev_otp_mode": config.settings.dev_otp_mode,
        # Set by auth.current_user, which runs as an app-wide dependency.
        "current_user": getattr(request.state, "user", None),
        "star_balance": getattr(request.state, "star_balance", None),
    }


def _filesize(size: int | None) -> str:
    if not size:
        return "—"
    if size < 1024 * 1024:
        return f"{size / 1024:.0f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


# Turkmenistan keeps UTC+5 all year, so a fixed offset is exact and needs no tz database.
ASHGABAT = timezone(timedelta(hours=5))


def _localtime(stored: str | None) -> str:
    """A stored UTC timestamp as the reader's local date and time: "23.09.2026 14:05"."""
    if not stored:
        return ""
    moment = datetime.strptime(stored, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return moment.astimezone(ASHGABAT).strftime("%d.%m.%Y %H:%M")


def _cover_url(book) -> str | None:
    """The cover's URL with a version, so a replaced cover is not hidden by the browser cache."""
    if not book["cover_path"]:
        return None
    return f"/{book['cover_path']}?v={quote(book['updated_at'] or '')}"


templates = Jinja2Templates(directory=BASE_DIR / "templates", context_processors=[_page_globals])
templates.env.filters["phone"] = format_phone
templates.env.filters["filesize"] = _filesize
templates.env.filters["localtime"] = _localtime
templates.env.globals["cover_url"] = _cover_url
