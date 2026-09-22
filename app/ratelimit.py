"""Rate limits on code requests (Sprint 03 task 5).

In Phase 1 this is anti-abuse; in Phase 2 every code is a paid SMS, so it becomes a financial
control (ADR-0006). The otp_codes table is the log: each issued code is one row carrying its
phone, source address and time, so no separate counter table is needed.

The source address is `request.client.host`. Behind nginx that is only the real client if
nginx sets X-Forwarded-For and uvicorn trusts it (uvicorn's default --forwarded-allow-ips is
127.0.0.1, which fits nginx on the same host). Without that every reader shares one address
and the per-address limit locks everyone out together.
"""
from __future__ import annotations

import math
import sqlite3
from datetime import datetime, timedelta, timezone

from app import config
from app.db import timestamp


class RateLimited(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(retry_after_seconds)
        self.retry_after_seconds = retry_after_seconds

    @property
    def message(self) -> str:
        minutes = math.ceil(self.retry_after_seconds / 60)
        if minutes >= 120:
            wait = f"{math.ceil(minutes / 60)} sagatdan"
        else:
            wait = f"{minutes} minutdan"
        return f"Kod gaty köp soraldy. {wait} soň täzeden synanyşyň."


def _parse(stored: str) -> datetime:
    return datetime.strptime(stored, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def check_code_request(conn: sqlite3.Connection, phone: str, ip: str | None) -> None:
    """Raise RateLimited if issuing one more code to this phone or address would exceed a limit.

    Deliberately never looks at the users table: a registered and an unregistered number must
    be limited, and answered, identically.
    """
    settings = config.settings
    checks = [("phone", phone, settings.otp_limits_per_phone)]
    if ip:
        checks.append(("request_ip", ip, settings.otp_limits_per_ip))

    retry_after = 0
    for column, value, limits in checks:
        for count, seconds in limits:
            since = timestamp(-timedelta(seconds=seconds))
            # The request becomes allowed again once enough of the in-window rows age out that
            # fewer than `count` remain: i.e. when row number (n - count), oldest first, leaves.
            rows = conn.execute(
                f"SELECT created_at FROM otp_codes WHERE {column} = ? AND created_at > ?"
                " ORDER BY created_at",
                (value, since),
            ).fetchall()
            if len(rows) < count:
                continue
            frees_at = _parse(rows[len(rows) - count]["created_at"]) + timedelta(seconds=seconds)
            wait = (frees_at - datetime.now(timezone.utc)).total_seconds()
            retry_after = max(retry_after, math.ceil(wait), 1)
    if retry_after:
        raise RateLimited(retry_after)


def prune(conn: sqlite3.Connection) -> None:
    """Delete code rows older than the longest window: no limit can see them any more."""
    settings = config.settings
    longest = max(seconds for _, seconds in settings.otp_limits_per_phone + settings.otp_limits_per_ip)
    longest = max(longest, settings.otp_ttl_seconds)
    conn.execute(
        "DELETE FROM otp_codes WHERE created_at < ?", (timestamp(-timedelta(seconds=longest)),)
    )
