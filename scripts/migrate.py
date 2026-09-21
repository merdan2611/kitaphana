"""Apply pending migrations to the configured database.

Usage (from the project root):
    python -m scripts.migrate

Forward-only, and safe to run twice: migrations already recorded in schema_migrations are
skipped. This is also the step deploy.sh runs on the server (ADR-0005, ADR-0016).
"""
from __future__ import annotations

from app.db import apply_migrations, connect


def main() -> None:
    conn = connect()
    try:
        applied = apply_migrations(conn)
    finally:
        conn.close()

    if applied:
        print(f"Applied {len(applied)} migration(s): {', '.join(applied)}")
    else:
        print("No pending migrations.")


if __name__ == "__main__":
    main()
