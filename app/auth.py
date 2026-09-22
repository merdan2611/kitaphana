"""Phone + one-time code authentication (Sprint 03, ADR-0006, ADR-0013).

Sign-up and sign-in are the same action. Everything here is what production runs, except
`deliver_code`, which is the one function Phase 2 replaces with real SMS.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import re
import secrets
import sqlite3
from datetime import timedelta
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from app import config, ratelimit, sessions
from app.db import get_db, timestamp
from app.phone import InvalidPhone, normalize_phone
from app.templating import templates

log = logging.getLogger(__name__)

MSG_CODE_FORMAT = "Kod 6 sanly bolmaly."
MSG_CODE_GONE = "Bu kodyň möhleti gutardy ýa-da ol eýýäm ulanyldy. Täze kod soraň."
MSG_CODE_BURNED = "Nädogry kod gaty köp girizildi. Täze kod soraň."
MSG_BLOCKED = "Bu hasap petiklenen."


class CodeRejected(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


# --- Codes -----------------------------------------------------------------------------------


def _hash_code(phone: str, code: str) -> str:
    # Keyed, because an unkeyed hash of a six-digit code is reversed by trying all million.
    key = config.settings.secret_key.encode()
    return hmac.new(key, f"{phone}:{code}".encode(), hashlib.sha256).hexdigest()


def request_code(conn: sqlite3.Connection, phone: str, ip: str | None) -> str:
    """Issue a fresh code for an already-normalised phone and return it (for delivery only).

    Raises ratelimit.RateLimited. Never consults the users table, so the outcome for a
    registered and an unregistered number is identical by construction.
    """
    conn.execute("BEGIN IMMEDIATE")  # the limit check and the insert must not interleave
    try:
        ratelimit.prune(conn)
        ratelimit.check_code_request(conn, phone, ip)
        now = timestamp()
        conn.execute(
            "UPDATE otp_codes SET used_at = ? WHERE phone = ? AND used_at IS NULL", (now, phone)
        )
        code = f"{secrets.randbelow(10**6):06d}"
        conn.execute(
            "INSERT INTO otp_codes (phone, code_hash, expires_at, created_at, request_ip)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                phone,
                _hash_code(phone, code),
                timestamp(timedelta(seconds=config.settings.otp_ttl_seconds)),
                now,
                ip,
            ),
        )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return code


def deliver_code(phone: str, code: str) -> str | None:
    """Get the code to the reader. Returns the code only if it is to be shown on screen.

    Phase 1 (ADR-0013): with dev-OTP mode on, the page shows it. Phase 2 replaces this body
    with an SMS send and returns None — nothing else in this module changes.
    """
    if config.settings.dev_otp_mode:
        return code
    log.warning("No SMS delivery exists yet and DEV_OTP_MODE is off: code for %s not sent", phone)
    return None


def verify_code(conn: sqlite3.Connection, phone: str, code: str) -> int:
    """Check a code for an already-normalised phone; return the user id, creating the account
    if this number has none. Raises CodeRejected with a reader-facing message."""
    code = re.sub(r"\s", "", code or "")
    if not re.fullmatch(r"[0-9]{6}", code):
        # Cannot be the code, so it does not spend an attempt.
        raise CodeRejected(MSG_CODE_FORMAT)

    now = timestamp()
    row = conn.execute(
        "SELECT id, code_hash FROM otp_codes"
        " WHERE phone = ? AND used_at IS NULL AND expires_at > ?"
        " ORDER BY id DESC LIMIT 1",
        (phone, now),
    ).fetchone()
    if row is None:
        raise CodeRejected(MSG_CODE_GONE)

    if not hmac.compare_digest(_hash_code(phone, code), row["code_hash"]):
        # Increment and burn in one statement, so concurrent guesses cannot overshoot the limit.
        max_attempts = config.settings.otp_max_attempts
        conn.execute(
            "UPDATE otp_codes SET attempt_count = attempt_count + 1,"
            " used_at = CASE WHEN attempt_count + 1 >= ? THEN ? ELSE used_at END"
            " WHERE id = ?",
            (max_attempts, now, row["id"]),
        )
        conn.commit()
        attempts = conn.execute(
            "SELECT attempt_count FROM otp_codes WHERE id = ?", (row["id"],)
        ).fetchone()["attempt_count"]
        remaining = max_attempts - attempts
        if remaining <= 0:
            raise CodeRejected(MSG_CODE_BURNED)
        raise CodeRejected(f"Kod nädogry. Ýene {remaining} synanyşygyňyz galdy.")

    # Claim the code; the used_at guard makes a concurrent second use of it fail here.
    claimed = conn.execute(
        "UPDATE otp_codes SET used_at = ? WHERE id = ? AND used_at IS NULL", (now, row["id"])
    ).rowcount
    if claimed != 1:
        conn.rollback()
        raise CodeRejected(MSG_CODE_GONE)

    conn.execute("INSERT OR IGNORE INTO users (phone) VALUES (?)", (phone,))
    user = conn.execute("SELECT id, is_blocked FROM users WHERE phone = ?", (phone,)).fetchone()
    conn.commit()
    if user["is_blocked"]:
        raise CodeRejected(MSG_BLOCKED)
    return user["id"]


# --- Dependencies ----------------------------------------------------------------------------


def current_user(request: Request, conn: sqlite3.Connection = Depends(get_db)) -> sqlite3.Row | None:
    """The signed-in reader, or None. Registered app-wide in main.py so templates always see it;
    FastAPI caches it per request, so depending on it again in a route costs nothing."""
    user = sessions.user_for_cookie(conn, request.cookies.get(sessions.COOKIE_NAME))
    request.state.user = user
    return user


def require_user(user: sqlite3.Row | None = Depends(current_user)) -> sqlite3.Row:
    if user is None:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user


def require_admin(user: sqlite3.Row | None = Depends(current_user)) -> sqlite3.Row:
    """Guard for admin routes. 404, not 403: a 403 would confirm the page exists."""
    if user is None or not user["is_admin"]:
        raise HTTPException(status_code=404)
    return user


# --- Pages -----------------------------------------------------------------------------------

router = APIRouter()


def safe_next(value: str | None) -> str | None:
    """Where to send a reader after login, if `value` is a path on this site; otherwise None.

    The value arrives in a URL (/login?next=/books/12), so without this check a crafted link such
    as /login?next=//evil.example would bounce a freshly logged-in reader to another site.
    """
    if not value or len(value) > 500:
        return None
    # "//host" and "/\host" are both read by browsers as another site.
    if not value.startswith("/") or value.startswith("//") or "\\" in value:
        return None
    if any(ch < " " or ch == "\x7f" for ch in value):
        return None
    parts = urlsplit(value)
    if parts.scheme or parts.netloc or parts.path.startswith(("/login", "/logout")):
        return None
    return value


def _login_page(request: Request, status_code: int = 200, **context):
    context.setdefault("step", "phone")
    return templates.TemplateResponse(request, "login.html", context, status_code=status_code)


@router.get("/login")
def login_form(
    request: Request,
    next_url: str = Query("", alias="next"),
    user=Depends(current_user),
):
    destination = safe_next(next_url)
    if user is not None:
        return RedirectResponse(destination or "/account", status_code=303)
    return _login_page(request, next_url=destination)


@router.post("/login")
def login_request_code(
    request: Request,
    phone: str = Form(""),
    next_url: str = Form("", alias="next"),
    conn: sqlite3.Connection = Depends(get_db),
):
    destination = safe_next(next_url)
    try:
        canonical = normalize_phone(phone)
    except InvalidPhone as exc:
        return _login_page(request, 400, phone=phone, error=exc.message, next_url=destination)

    ip = request.client.host if request.client else None
    try:
        code = request_code(conn, canonical, ip)
    except ratelimit.RateLimited as exc:
        return _login_page(request, 429, phone=phone, error=exc.message, next_url=destination)

    return _login_page(
        request,
        step="code",
        phone=canonical,
        shown_code=deliver_code(canonical, code),
        next_url=destination,
    )


@router.post("/login/verify")
def login_verify(
    request: Request,
    phone: str = Form(""),
    code: str = Form(""),
    next_url: str = Form("", alias="next"),
    conn: sqlite3.Connection = Depends(get_db),
):
    destination = safe_next(next_url)
    try:
        canonical = normalize_phone(phone)
    except InvalidPhone as exc:
        return _login_page(request, 400, phone=phone, error=exc.message, next_url=destination)

    try:
        user_id = verify_code(conn, canonical, code)
    except CodeRejected as exc:
        return _login_page(
            request, 400, step="code", phone=canonical, error=exc.message, next_url=destination
        )

    cookie = sessions.create_session(conn, user_id)
    conn.commit()
    response = RedirectResponse(destination or "/account", status_code=303)
    sessions.set_session_cookie(response, cookie)
    return response


@router.get("/account")
def account(request: Request, user=Depends(require_user)):
    return templates.TemplateResponse(request, "account.html", {"user": user})


@router.post("/logout")
def logout(request: Request, conn: sqlite3.Connection = Depends(get_db)):
    sessions.delete_session(conn, request.cookies.get(sessions.COOKIE_NAME))
    response = RedirectResponse("/", status_code=303)
    sessions.clear_session_cookie(response)
    return response
