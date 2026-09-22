"""SQLite connection handling and the migration runner (ADR-0001, ADR-0016).

Concurrency decision (ADR-0001, Sprint 01 task 3): route handlers in this project are plain
`def`, not `async def`. FastAPI runs a sync path operation in a worker thread pool
automatically, which keeps these blocking sqlite3 calls off the event loop without any manual
`run_in_executor` bookkeeping. An `async def` handler that called sqlite3 directly would run on
the event loop and stall every other request for the duration of the query. This is decided
once, here, and followed everywhere else in the project.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from app import config
from app.config import BASE_DIR
from app.search import fold

BUSY_TIMEOUT_MS = 5000

MIGRATIONS_DIR = BASE_DIR / "migrations"


def connect(database_path: Path | str | None = None) -> sqlite3.Connection:
    """Open a connection with this project's required pragmas already set."""
    # Read at call time, not import time, so tests can point every connection at their own file.
    path = Path(database_path) if database_path is not None else config.settings.database_path
    path.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False: FastAPI opens a request's connection (the get_db dependency) and
    # runs the handler in separate thread-pool calls, which may land on different threads. Each
    # connection still belongs to one request and is used by one thread at a time.
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    # The search folding function (app/search.py), callable from SQL. Migration 004 uses it to
    # fill books.search_text for books that existed before the column did.
    conn.create_function("kitaphana_fold", 1, fold, deterministic=True)
    return conn


def timestamp(offset: timedelta = timedelta()) -> str:
    """UTC now (plus `offset`) in the same text format as SQLite's datetime('now').

    Every stored time uses this one format, so comparing them as strings in SQL is correct.
    """
    moment = datetime.now(timezone.utc) + offset
    return moment.strftime("%Y-%m-%d %H:%M:%S")


def get_db() -> Iterator[sqlite3.Connection]:
    """FastAPI dependency: yields a connection and always closes it."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def _ensure_schema_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            filename TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )


def _migration_number(filename: str) -> int:
    return int(filename.split("-", 1)[0])


def apply_migrations(conn: sqlite3.Connection) -> list[str]:
    """Apply any migrations/*.sql not yet recorded, in filename order. Safe to run twice."""
    _ensure_schema_migrations_table(conn)
    applied = {row["filename"] for row in conn.execute("SELECT filename FROM schema_migrations")}

    newly_applied: list[str] = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if path.name in applied:
            continue
        conn.executescript(path.read_text())
        conn.execute("INSERT INTO schema_migrations (filename) VALUES (?)", (path.name,))
        conn.commit()
        newly_applied.append(path.name)
    return newly_applied


def current_migration_version(conn: sqlite3.Connection) -> int | None:
    """The highest applied migration number, or None if none have run yet."""
    _ensure_schema_migrations_table(conn)
    rows = conn.execute("SELECT filename FROM schema_migrations").fetchall()
    if not rows:
        return None
    return max(_migration_number(row["filename"]) for row in rows)
