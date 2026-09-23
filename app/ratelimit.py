"""Rate limits on code requests (Sprint 03 task 5), and the arithmetic downloads share (Sprint 06).

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
        return f"Kod gaty köp soraldy. {wait_phrase(self.retry_after_seconds)} soň täzeden synanyşyň."


def wait_phrase(seconds: int) -> str:
    """"5 minutdan" or "3 sagatdan": how long to wait, for "… soň täzeden synanyşyň"."""
    minutes = math.ceil(seconds / 60)
    if minutes >= 120:
        return f"{math.ceil(minutes / 60)} sagatdan"
    return f"{minutes} minutdan"


def _parse(stored: str) -> datetime:
    return datetime.strptime(stored, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def seconds_until_allowed(times: list[str], count: int, seconds: int) -> int:
    """0 if one more event is within the limit, else how many seconds until it is (at least 1).

    `times` are the stored timestamps of the events inside the window, oldest first. The next
    event becomes allowed once enough of them age out that fewer than `count` remain: i.e. when
    event number (n - count), oldest first, leaves the window.
    """
    if len(times) < count:
        return 0
    frees_at = _parse(times[len(times) - count]) + timedelta(seconds=seconds)
    wait = (frees_at - datetime.now(timezone.utc)).total_seconds()
    return max(math.ceil(wait), 1)


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
            rows = conn.execute(
                f"SELECT created_at FROM otp_codes WHERE {column} = ? AND created_at > ?"
                " ORDER BY created_at",
                (value, since),
            ).fetchall()
            times = [row["created_at"] for row in rows]
            retry_after = max(retry_after, seconds_until_allowed(times, count, seconds))
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
