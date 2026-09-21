from __future__ import annotations

import sqlite3

import pytest

from app.db import apply_migrations, connect


def test_connection_enables_wal_and_foreign_keys(db_path):
    conn = connect(db_path)
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        conn.close()


def test_wal_file_appears_on_disk_after_a_write(db_path):
    # Checked with the connection still open: SQLite checkpoints and removes the -wal file
    # when the last connection to a database closes cleanly, so closing first would defeat
    # the point of this check.
    conn = connect(db_path)
    try:
        apply_migrations(conn)
        conn.execute("INSERT INTO users (phone) VALUES ('+99361234567')")
        conn.commit()
        assert db_path.with_name(db_path.name + "-wal").exists()
    finally:
        conn.close()


def test_duplicate_phone_is_rejected_by_the_database(db_path):
    conn = connect(db_path)
    try:
        apply_migrations(conn)
        conn.execute("INSERT INTO users (phone) VALUES ('+99361234567')")
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO users (phone) VALUES ('+99361234567')")
    finally:
        conn.close()


def test_duplicate_content_hash_is_rejected_by_the_database(db_path):
    conn = connect(db_path)
    try:
        apply_migrations(conn)
        conn.execute(
            "INSERT INTO books (title, author, language, content_hash, file_size)"
            " VALUES ('Title', 'Author', 'tk', 'samehash', 1000)"
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO books (title, author, language, content_hash, file_size)"
                " VALUES ('Other', 'Other Author', 'tk', 'samehash', 2000)"
            )
    finally:
        conn.close()
