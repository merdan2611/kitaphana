"""Stars: the append-only ledger and everything that reads it (Sprint 06, ADR-0007).

THE RULE THIS WHOLE DESIGN RESTS ON: every star movement is one new row in star_ledger, written
by `append_entry` below, inside `transaction`. Nothing else in the codebase writes to that table,
and nothing anywhere updates or deletes a row in it (migration 005 makes SQLite refuse both). A
balance is the sum of a reader's rows and is never stored. A mistake is corrected by appending a
row in the opposite direction, so the mistake and its correction both stay on record.

All SQL that touches star_ledger lives in this module, reads included; tests/test_stars.py
checks that no other module mentions the table.

No entry may take a balance below zero. Because the balance check and the insert run in one
`BEGIN IMMEDIATE` transaction, two downloads started at the same moment cannot both pass a check
that only one of them should pass.
"""
from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from typing import Iterator

REASONS = ("grant", "topup", "spend", "refund")

_BOOK_REFERENCE = re.compile(r"book:([0-9]+)")

# Connections currently inside `transaction`, by id(). sqlite3 connections cannot carry extra
# attributes or weak references; an id is only reused after its object is gone, and every id is
# removed again before `transaction` returns.
_locked: set[int] = set()


class InsufficientStars(Exception):
    """The entry would take the reader's balance below zero. Nothing was written."""

    def __init__(self, balance: int, needed: int) -> None:
        super().__init__(f"balance {balance}, needed {needed}")
        self.balance = balance
        self.needed = needed


def book_reference(book_id: int) -> str:
    return f"book:{book_id}"


# --- Writing ---------------------------------------------------------------------------------


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[None]:
    """The write transaction every ledger entry is appended in; commits on success.

    BEGIN IMMEDIATE takes SQLite's write lock before anything is read, so whatever the caller
    reads inside (a balance, earlier downloads) cannot change before its row is written. A second
    caller waits for the lock (up to busy_timeout, app/db.py) and then sees the first one's row.
    """
    if conn.in_transaction:
        # Committing or rolling back someone else's half-finished work here would be a bug
        # either way; refuse loudly instead.
        raise RuntimeError("stars.transaction needs a connection with no open transaction")
    conn.execute("BEGIN IMMEDIATE")
    _locked.add(id(conn))
    try:
        yield
    except BaseException:
        conn.rollback()
        raise
    else:
        conn.commit()
    finally:
        _locked.discard(id(conn))


def append_entry(
    conn: sqlite3.Connection,
    user_id: int,
    amount: int,
    reason: str,
    reference: str | None = None,
    note: str | None = None,
) -> int:
    """Append one row and return its id. The only function that writes to star_ledger.

    Must run inside `transaction(conn)`. Raises InsufficientStars, writing nothing, when a
    negative amount is more than the reader has; ValueError for an entry that breaks the rules
    in migration 005 (checked here too, so the mistake names itself).
    """
    if id(conn) not in _locked:
        raise RuntimeError("append_entry must run inside stars.transaction(conn)")
    if reason not in REASONS:
        raise ValueError(f"unknown ledger reason: {reason!r}")
    if not isinstance(amount, int) or isinstance(amount, bool):
        raise ValueError(f"amount must be a whole number of stars: {amount!r}")
    if reason == "grant" and amount == 0:
        raise ValueError("a grant must add or take away at least one star")
    if reason in ("topup", "refund") and amount <= 0:
        raise ValueError(f"a {reason} must be positive")
    if reason == "spend" and amount > 0:
        raise ValueError("a spend cannot add stars")
    if reason in ("spend", "refund") and not reference:
        raise ValueError(f"a {reason} must say what it was for")
    if reason == "grant" and not (note and note.strip()):
        raise ValueError("a grant must carry the admin's note")

    if amount < 0:
        current = balance(conn, user_id)
        if current + amount < 0:
            raise InsufficientStars(balance=current, needed=-amount)

    cursor = conn.execute(
        "INSERT INTO star_ledger (user_id, amount, reason, reference, note) VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, reason, reference, note),
    )
    return cursor.lastrowid


def grant(conn: sqlite3.Connection, user_id: int, amount: int, note: str) -> int:
    """An admin adding (or, when negative, correcting away) stars by hand."""
    with transaction(conn):
        return append_entry(conn, user_id, amount, "grant", note=note.strip())


# --- Reading ---------------------------------------------------------------------------------


def balance(conn: sqlite3.Connection, user_id: int) -> int:
    return conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM star_ledger WHERE user_id = ?", (user_id,)
    ).fetchone()[0]


def has_paid_for(conn: sqlite3.Connection, user_id: int, book_id: int) -> bool:
    """True if the reader's spends on this book, less refunds for it, come to more than zero.

    A book paid for once downloads again for free; once refunded, it has to be paid for again.
    """
    paid = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM star_ledger"
        " WHERE user_id = ? AND reference = ? AND reason IN ('spend', 'refund')",
        (user_id, book_reference(book_id)),
    ).fetchone()[0]
    return paid < 0


def has_downloaded(conn: sqlite3.Connection, user_id: int, book_id: int) -> bool:
    """True if the reader has a recorded download of this book, paid or free."""
    row = conn.execute(
        "SELECT 1 FROM star_ledger WHERE user_id = ? AND reference = ? AND reason = 'spend' LIMIT 1",
        (user_id, book_reference(book_id)),
    ).fetchone()
    return row is not None


def download_times(conn: sqlite3.Connection, user_id: int, since: str) -> list[str]:
    """When the reader's downloads after `since` were recorded, oldest first (for rate limits).

    Every download writes a spend row, free ones included, so the ledger is the download log.
    """
    rows = conn.execute(
        "SELECT created_at FROM star_ledger"
        " WHERE user_id = ? AND reason = 'spend' AND reference LIKE 'book:%' AND created_at > ?"
        " ORDER BY created_at, id",
        (user_id, since),
    ).fetchall()
    return [row["created_at"] for row in rows]


def history(conn: sqlite3.Connection, user_id: int) -> list[dict]:
    """Every entry for the reader, newest first, each with the balance it left behind.

    `book_id` is set when the entry refers to a book that is still published, so the page can
    link to it; the note keeps the title either way.
    """
    rows = conn.execute(
        "SELECT * FROM star_ledger WHERE user_id = ? ORDER BY id", (user_id,)
    ).fetchall()
    book_ids = {_book_id(row["reference"]) for row in rows} - {None}
    published: set[int] = set()
    ids = sorted(book_ids)
    for start in range(0, len(ids), 500):  # stay well under SQLite's bound-parameter limit
        chunk = ids[start : start + 500]
        placeholders = ",".join("?" * len(chunk))
        published.update(
            row["id"]
            for row in conn.execute(f"SELECT id FROM published_books WHERE id IN ({placeholders})", chunk)
        )

    entries = []
    running = 0
    for row in rows:
        running += row["amount"]
        book_id = _book_id(row["reference"])
        entries.append(
            {**dict(row), "balance_after": running, "book_id": book_id if book_id in published else None}
        )
    entries.reverse()
    return entries


def _book_id(reference: str | None) -> int | None:
    match = _BOOK_REFERENCE.fullmatch(reference or "")
    return int(match.group(1)) if match else None


def recent_entries(conn: sqlite3.Connection, limit: int = 20) -> list[sqlite3.Row]:
    """The newest entries across all readers, with each reader's phone, for the admin."""
    return conn.execute(
        "SELECT star_ledger.*, users.phone FROM star_ledger JOIN users ON users.id = star_ledger.user_id"
        " ORDER BY star_ledger.id DESC LIMIT ?",
        (limit,),
    ).fetchall()
