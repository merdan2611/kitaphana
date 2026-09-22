"""Login sessions (Sprint 03 task 6).

The cookie holds `<token>.<signature>`: a 256-bit random token plus an HMAC of it keyed with
SECRET_KEY. A tampered cookie fails the signature check before the database is touched. The
database stores only SHA-256(token), so a leaked database cannot be replayed as cookies.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
from datetime import timedelta

from fastapi import Response

from app import config
from app.db import timestamp

COOKIE_NAME = "kitaphana_session"

# last_seen_at is informational; refreshing it at most this often keeps a page view from being
# a database write every time.
LAST_SEEN_RESOLUTION = timedelta(hours=1)


def _sign(token: str) -> str:
    key = config.settings.secret_key.encode()
    return hmac.new(key, token.encode(), hashlib.sha256).hexdigest()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _token_from_cookie(cookie: str | None) -> str | None:
    """The token if the cookie is well-formed and correctly signed, else None."""
    if not cookie or "." not in cookie:
        return None
    token, signature = cookie.rsplit(".", 1)
    if not hmac.compare_digest(signature, _sign(token)):
        return None
    return token


def create_session(conn: sqlite3.Connection, user_id: int) -> str:
    """Store a new session and return the cookie value. The caller commits."""
    token = secrets.token_urlsafe(32)
    ttl = timedelta(days=config.settings.session_ttl_days)
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
        (_hash_token(token), user_id, timestamp(ttl)),
    )
    return f"{token}.{_sign(token)}"


def user_for_cookie(conn: sqlite3.Connection, cookie: str | None) -> sqlite3.Row | None:
    """The signed-in, non-blocked user for this cookie, or None for anything else."""
    token = _token_from_cookie(cookie)
    if token is None:
        return None
    token_hash = _hash_token(token)
    row = conn.execute(
        "SELECT users.*, sessions.expires_at AS session_expires_at,"
        " sessions.last_seen_at AS session_last_seen_at"
        " FROM sessions JOIN users ON users.id = sessions.user_id"
        " WHERE sessions.token_hash = ?",
        (token_hash,),
    ).fetchone()
    if row is None:
        return None
    if row["session_expires_at"] <= timestamp():
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
        conn.commit()
        return None
    if row["is_blocked"]:
        return None
    if row["session_last_seen_at"] <= timestamp(-LAST_SEEN_RESOLUTION):
        conn.execute(
            "UPDATE sessions SET last_seen_at = ? WHERE token_hash = ?", (timestamp(), token_hash)
        )
        conn.commit()
    return row


def delete_session(conn: sqlite3.Connection, cookie: str | None) -> None:
    """End the session server-side, so the cookie is worthless even if something kept it."""
    token = _token_from_cookie(cookie)
    if token is None:
        return
    conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_hash_token(token),))
    conn.commit()


def set_session_cookie(response: Response, cookie: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        cookie,
        # A max-age makes it a persistent cookie, so it survives a browser restart.
        max_age=config.settings.session_ttl_days * 86400,
        httponly=True,
        secure=config.settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        COOKIE_NAME, httponly=True, secure=config.settings.cookie_secure, samesite="lax", path="/"
    )
