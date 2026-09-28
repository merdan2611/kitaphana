"""The one Jinja2Templates instance, with the values every page needs.

`dev_otp_mode`, `current_user` and `star_balance` come from a context processor rather than each
handler, so no page can forget the dev-mode banner (ADR-0013) or the signed-in header.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app import config, i18n
from app.config import BASE_DIR
from app.i18n import tr, tr_n
from app.phone import format_phone


def _page_globals(request: Request) -> dict:
    return {
        "dev_otp_mode": config.settings.dev_otp_mode,
        # Set by auth.current_user, which runs as an app-wide dependency.
        "current_user": getattr(request.state, "user", None),
        "star_balance": getattr(request.state, "star_balance", None),
        # The interface language (app/i18n.py): <html lang> and the language switch.
        "ui_lang": i18n.current(),
        "ui_languages": i18n.LANGUAGES,
        "ui_short_names": i18n.SHORT_NAMES,
    }


def _filesize(size: int | None) -> str:
    if not size:
        return "—"
    if size < 1024 * 1024:
        return f"{size / 1024:.0f} KB"
    if size < 1024**3:
        return f"{size / (1024 * 1024):.1f} MB"
    return f"{size / 1024**3:.1f} GB"  # disk figures on the admin overview


# Turkmenistan keeps UTC+5 all year, so a fixed offset is exact and needs no tz database.
ASHGABAT = timezone(timedelta(hours=5))


def _localtime(stored: str | None) -> str:
    """A stored UTC timestamp as the reader's local date and time: "23.09.2026 14:05"."""
    if not stored:
        return ""
    moment = datetime.strptime(stored, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return moment.astimezone(ASHGABAT).strftime("%d.%m.%Y %H:%M")


def _ago(stored: str | None) -> str:
    """How long ago a stored UTC timestamp was, in words, in the reader's language: "3 gün öň",
    "3 дня назад"."""
    if not stored:
        return ""
    moment = datetime.strptime(stored, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    seconds = max((datetime.now(timezone.utc) - moment).total_seconds(), 0)
    minutes, hours, days = seconds / 60, seconds / 3600, seconds / 86400
    if minutes < 1:
        return tr("häzir")
    if hours < 1:
        return tr_n("%(num)d minut öň", int(minutes))
    if days < 1:
        return tr_n("%(num)d sagat öň", int(hours))
    if days < 7:
        return tr_n("%(num)d gün öň", int(days))
    if days < 30:
        return tr_n("%(num)d hepde öň", int(days // 7))
    if days < 365:
        return tr_n("%(num)d aý öň", int(days // 30))
    return tr_n("%(num)d ýyl öň", int(days // 365))


def _cover_url(book) -> str | None:
    """The cover's URL with a version, so a replaced cover is not hidden by the browser cache."""
    if not book["cover_path"]:
        return None
    return f"/{book['cover_path']}?v={quote(book['updated_at'] or '')}"


STATIC_DIR = BASE_DIR / "static"
_static_versions: dict[str, tuple[int, str]] = {}


def _static_url(path: str) -> str:
    """/static/<path>?v=<content hash>, so a browser that cached the old file fetches the new
    one the moment it changes, instead of showing new pages with old styles."""
    file = STATIC_DIR / path
    mtime = file.stat().st_mtime_ns
    cached = _static_versions.get(path)
    if cached is None or cached[0] != mtime:
        cached = (mtime, hashlib.sha256(file.read_bytes()).hexdigest()[:10])
        _static_versions[path] = cached
    return f"/static/{quote(path)}?v={cached[1]}"


templates = Jinja2Templates(directory=BASE_DIR / "templates", context_processors=[_page_globals])
# Reader pages mark their text with _() and {% trans %} (ADR-0021). Newstyle: _() takes its
# placeholders as keyword arguments. Trimmed: a {% trans %} block spread over lines in the
# template is one line of text, so the catalogue key does not depend on indentation.
templates.env.add_extension("jinja2.ext.i18n")
templates.env.install_gettext_callables(i18n.gettext, i18n.ngettext, newstyle=True)
templates.env.policies["ext.i18n.trimmed"] = True
templates.env.filters["phone"] = format_phone
templates.env.filters["filesize"] = _filesize
templates.env.filters["localtime"] = _localtime
templates.env.filters["ago"] = _ago
templates.env.globals["cover_url"] = _cover_url
templates.env.globals["static_url"] = _static_url
