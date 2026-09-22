from __future__ import annotations

from app.db import MIGRATIONS_DIR, apply_migrations, connect, current_migration_version

ALL_MIGRATIONS = sorted(p.name for p in MIGRATIONS_DIR.glob("*.sql"))
LATEST = int(ALL_MIGRATIONS[-1].split("-", 1)[0])


def test_migrate_applies_on_an_empty_database_then_is_a_noop(db_path):
    conn = connect(db_path)
    try:
        first_run = apply_migrations(conn)
        assert first_run == ALL_MIGRATIONS
        assert current_migration_version(conn) == LATEST

        second_run = apply_migrations(conn)
        assert second_run == []
        assert current_migration_version(conn) == LATEST
    finally:
        conn.close()


def test_migrate_creates_the_spine_tables(db_path):
    conn = connect(db_path)
    try:
        apply_migrations(conn)
        tables = {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert {"users", "books", "otp_codes", "sessions"}.issubset(tables)
    finally:
        conn.close()
