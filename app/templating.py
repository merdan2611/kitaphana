"""The one Jinja2Templates instance, with the values every page needs.

`dev_otp_mode` and `current_user` come from a context processor rather than each handler, so
no page can forget the dev-mode banner (ADR-0013) or the signed-in header.
"""
from __future__ import annotations

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
    }


templates = Jinja2Templates(directory=BASE_DIR / "templates", context_processors=[_page_globals])
templates.env.filters["phone"] = format_phone
