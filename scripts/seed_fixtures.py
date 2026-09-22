"""Load the placeholder books in fixtures/books/ into the configured database (ADR-0017).

Usage (from the project root, after `python -m scripts.migrate`):
    python -m scripts.seed_fixtures

Every file goes through storage.ingest_path — the same staging, hashing, de-duplication and
cover rendering an admin upload uses — never a raw INSERT. Running it twice is a no-op: the
second run finds every file already present by content hash.

It refuses to run if the database holds any book that is not a fixture. Placeholder books must
never be able to reach a real catalogue through an accidental re-run.
"""
from __future__ import annotations

import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from app import storage
from app.config import BASE_DIR
from app.db import connect

MANIFEST = BASE_DIR / "fixtures" / "books" / "manifest.yaml"


class RefuseToSeed(Exception):
    pass


@dataclass
class SeedResult:
    added: list[str]
    skipped: list[str]


def load_manifest(path: Path) -> list[dict]:
    entries = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    for entry in entries:
        for key in ("filename", "title", "language", "source"):
            if not str(entry.get(key) or "").strip():
                raise RefuseToSeed(
                    f"{path.name}: entry {entry.get('filename', '?')!r} has no {key!r}. "
                    "Every fixture needs its provenance recorded (fixtures/README.md)."
                )
    return entries


def seed(conn: sqlite3.Connection, manifest: Path = MANIFEST) -> SeedResult:
    real_books = conn.execute("SELECT COUNT(*) FROM books WHERE is_fixture = 0").fetchone()[0]
    if real_books:
        raise RefuseToSeed(
            f"Refusing to seed: this database already holds {real_books} real (non-fixture) "
            "book(s). Fixtures are for an empty development database only."
        )

    result = SeedResult(added=[], skipped=[])
    for entry in load_manifest(manifest):
        path = manifest.parent / entry["filename"]
        try:
            storage.ingest_path(
                conn,
                path,
                title=str(entry["title"]),
                author=str(entry.get("author") or ""),
                year=entry.get("year"),
                language=entry["language"],
                description=str(entry.get("description") or ""),
                price_stars=int(entry.get("price_stars") or 0),
                is_published=bool(entry.get("published", True)),
                is_fixture=True,
            )
        except storage.Duplicate:
            result.skipped.append(entry["filename"])
        else:
            result.added.append(entry["filename"])
    return result


def main() -> int:
    conn = connect()
    try:
        result = seed(conn)
    except RefuseToSeed as exc:
        print(exc, file=sys.stderr)
        return 1
    finally:
        conn.close()

    for name in result.added:
        print(f"added    {name}")
    for name in result.skipped:
        print(f"present  {name}")
    print(f"{len(result.added)} added, {len(result.skipped)} already present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
