"""The figures on the admin overview page (Sprint 08, task 4): who is using the site, what they
download, and how much disk and memory are left.

Only data the app already records. Visits are not counted: anonymous page views exist only in
nginx's log, which the sandboxed app cannot read, and parsing it on every page load would grow
slow with the log. That waits for Phase 2. Everything here is a few counts over small tables,
run only when the admin opens the page.

A figure that cannot be read — no /proc outside Linux, say — is None, and the page shows "—".
"""
from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

from app import config, requests, stars
from app.db import current_migration_version, timestamp
from app.templating import ASHGABAT

# Module-level so tests can point them at a directory that lacks them.
PROC = Path("/proc")
CGROUP_ROOT = Path("/sys/fs/cgroup")

# Warn well before either runs out: a 50 GB disk and 2 GB of RAM (ADR-0019).
DISK_LOW_FRACTION = 0.10
DISK_LOW_BYTES = 5 * 1024**3
MEMORY_LOW_BYTES = 200 * 1024**2

DAY = timedelta(days=1)
WEEK = timedelta(days=7)


def _count(conn: sqlite3.Connection, sql: str, *params) -> int:
    return conn.execute(sql, params).fetchone()[0] or 0


# --- Activity --------------------------------------------------------------------------------


def activity(conn: sqlite3.Connection) -> dict:
    """Readers, sign-ins, downloads, stars and requests, over the last day and week.

    "Active" is a reader whose session was used in the window. last_seen_at is refreshed at most
    hourly (app/sessions.py) and goes with the session on logout, so it slightly undercounts.
    Every download writes one ledger row, free re-downloads included, so rows are downloads.
    """
    day, week = timestamp(-DAY), timestamp(-WEEK)

    def active(since: str) -> int:
        return _count(conn, "SELECT COUNT(DISTINCT user_id) FROM sessions WHERE last_seen_at >= ?", since)

    def logins(since: str) -> dict:
        codes = _count(conn, "SELECT COUNT(*) FROM otp_codes WHERE created_at >= ?", since)
        sign_ins = _count(
            conn, "SELECT COUNT(*) FROM otp_codes WHERE created_at >= ? AND used_at IS NOT NULL", since
        )
        # Numbers that asked for a code and never got in: the friction Sprint 08 task 8 is after.
        stuck = _count(
            conn,
            "SELECT COUNT(DISTINCT phone) FROM otp_codes WHERE created_at >= ?1 AND phone NOT IN"
            " (SELECT phone FROM otp_codes WHERE created_at >= ?1 AND used_at IS NOT NULL)",
            since,
        )
        return {"codes": codes, "sign_ins": sign_ins, "stuck": stuck}

    star_totals = stars.totals(conn)

    return {
        "readers": _count(conn, "SELECT COUNT(*) FROM users"),
        "readers_new_week": _count(conn, "SELECT COUNT(*) FROM users WHERE created_at >= ?", week),
        "active_day": active(day),
        "active_week": active(week),
        "downloads_day": stars.download_count(conn, day),
        "downloads_week": stars.download_count(conn, week),
        "downloads_total": stars.download_count(conn),
        "logins_day": logins(day),
        "logins_week": logins(week),
        "stars_added": star_totals["added"],
        "stars_spent": star_totals["spent"],
        "stars_held": star_totals["held"],
        "requests_open": requests.open_counts(conn).get("open", 0),
        "requests_new_week": _count(conn, "SELECT COUNT(*) FROM requests WHERE created_at >= ?", week),
        "upvotes_week": _count(conn, "SELECT COUNT(*) FROM request_upvotes WHERE created_at >= ?", week),
    }


BAR_STEPS = 20  # bar heights in 5 % steps: CSS classes, since the pages use no inline styles


def bar_step(value: int, peak: int) -> int:
    """A bar's height class, 0-BAR_STEPS. Any non-zero value gets at least one step."""
    if not value or not peak:
        return 0
    return max(1, round(value * BAR_STEPS / peak))


def daily(conn: sqlite3.Connection, days: int = 14) -> dict:
    """Sign-ups and downloads per Ashgabat calendar day, oldest first, today last.

    Each series carries its own peak: the two are counted on their own scales, drawn as two
    charts rather than one chart with two axes.
    """
    today = datetime.now(ASHGABAT).date()
    first = today - timedelta(days=days - 1)
    since = (
        datetime.combine(first, time(), ASHGABAT).astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    )
    # Stored times are UTC; Turkmenistan is UTC+5 all year, so shifting by five hours is exact.
    shift = "+5 hours"
    signups = dict(conn.execute(
        "SELECT date(created_at, ?), COUNT(*) FROM users WHERE created_at >= ? GROUP BY 1", (shift, since)
    ).fetchall())
    downloads = stars.downloads_per_day(conn, since, shift)
    dates = [first + timedelta(days=offset) for offset in range(days)]

    def series(counts: dict) -> dict:
        values = [counts.get(day.isoformat(), 0) for day in dates]
        peak = max(values)
        return {
            "total": sum(values),
            "peak": peak,
            "days": [
                {"label": day.strftime("%d.%m"), "value": value, "step": bar_step(value, peak)}
                for day, value in zip(dates, values)
            ],
        }

    return {"signups": series(signups), "downloads": series(downloads)}


def top_books(conn: sqlite3.Connection, limit: int = 5) -> list[sqlite3.Row]:
    """The most downloaded books (stars.most_downloaded: the ledger is read only there)."""
    return stars.most_downloaded(conn, limit)


def newest_readers(conn: sqlite3.Connection, limit: int = 5) -> list[dict]:
    """The latest sign-ups, with when each was last seen and their star balance."""
    rows = conn.execute(
        "SELECT users.id, users.phone, users.created_at,"
        " (SELECT MAX(last_seen_at) FROM sessions WHERE sessions.user_id = users.id) AS last_seen_at"
        " FROM users ORDER BY users.id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [{**dict(row), "balance": stars.balance(conn, row["id"])} for row in rows]


# --- Server ----------------------------------------------------------------------------------


def _read(path: Path) -> str | None:
    try:
        return path.read_text()
    except OSError:
        return None


def _kib_field(text: str | None, name: str) -> int | None:
    """A "Name:   1234 kB" line from /proc/meminfo or /proc/self/status, in bytes."""
    for line in (text or "").splitlines():
        key, _, value = line.partition(":")
        if key == name:
            return int(value.split()[0]) * 1024
    return None


def _cgroup_memory_limit() -> int | None:
    """This service's MemoryMax (deploy/kitaphana.service), or None when there is none."""
    cgroup = _read(PROC / "self" / "cgroup")
    if not cgroup or not cgroup.startswith("0::"):
        return None
    limit = _read(CGROUP_ROOT / cgroup.strip()[3:].lstrip("/") / "memory.max")
    return int(limit) if limit and limit.strip().isdigit() else None


def _file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def server(conn: sqlite3.Connection, db_path: Path, media_root: Path) -> dict:
    """Disk, memory and database figures, with a warning flag for each that is running low."""
    try:
        disk = shutil.disk_usage(media_root)
    except OSError:
        disk = None
    meminfo = _read(PROC / "meminfo")
    uptime = _read(PROC / "uptime")
    pdfs = conn.execute("SELECT COUNT(*) AS n, COALESCE(SUM(file_size), 0) AS size FROM books").fetchone()

    figures = {
        "disk_total": disk.total if disk else None,
        "disk_used": disk.used if disk else None,
        "disk_free": disk.free if disk else None,
        "db_size": _file_size(db_path) + _file_size(db_path.with_name(db_path.name + "-wal")),
        "pdf_count": pdfs["n"],
        "pdf_size": pdfs["size"],
        "memory_total": _kib_field(meminfo, "MemTotal"),
        "memory_available": _kib_field(meminfo, "MemAvailable"),
        "app_memory": _kib_field(_read(PROC / "self" / "status"), "VmRSS"),
        "app_memory_limit": _cgroup_memory_limit(),
        "uptime_seconds": int(float(uptime.split()[0])) if uptime else None,
        "version": config.settings.app_version,
        "migration": current_migration_version(conn),
    }
    figures["disk_low"] = bool(disk) and (
        disk.free < DISK_LOW_BYTES or disk.free < disk.total * DISK_LOW_FRACTION
    )
    figures["memory_low"] = (
        figures["memory_available"] is not None and figures["memory_available"] < MEMORY_LOW_BYTES
    )
    return figures
