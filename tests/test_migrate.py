from __future__ import annotations

from app.db import apply_migrations, connect, current_migration_version


def test_migrate_applies_on_an_empty_database_then_is_a_noop(db_path):
    conn = connect(db_path)
    try:
        first_run = apply_migrations(conn)
        assert first_run == ["001-initial.sql"]
        assert current_migration_version(conn) == 1

        second_run = apply_migrations(conn)
        assert second_run == []
        assert current_migration_version(conn) == 1
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
        assert {"users", "books"}.issubset(tables)
    finally:
        conn.close()
