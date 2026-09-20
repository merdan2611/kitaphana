# ADR-0016: SQLite in WAL mode with plain SQL migrations

- **Status**: Accepted
- **Date**: 2026-09-20

## Context

[ADR-0001](0001-fastapi-and-sqlite.md) chose SQLite. Two operational details follow from it that
are much cheaper to settle in Sprint 01 than to retrofit later: how concurrent access behaves,
and how the schema changes over time.

SQLite's default journal mode makes readers and writers block one another, so a single write
stalls every page being served at that moment. And a database whose schema evolves by being
edited by hand on the server is a database that will eventually differ from the one on the
developer's machine, in a way nobody notices until something breaks in production only.

## Decision

**WAL mode**, enabled at startup on every connection, together with a `busy_timeout` so that a
connection waiting on a write waits briefly instead of failing immediately. Foreign key
enforcement is switched on explicitly, since SQLite leaves it off by default.

**Migrations are numbered SQL files** in a `migrations/` directory — `001-initial.sql`,
`002-add-book-price.sql` — applied in order by a small script that records which have run in a
`schema_migrations` table. Forward-only: a mistake is corrected by a new migration, never by
editing one that has already been applied anywhere.

No ORM migration framework. The script is perhaps thirty lines.

## Consequences

### Positive

- With WAL, reads do not block on writes. Somebody signing up does not stall everyone browsing.
- WAL is also markedly faster for the write pattern here: many small appends to the ledger.
- Numbered SQL files mean the schema's history is in git and legible, and the production schema
  is reconstructible from the repository alone.
- Applying migrations is a step in `deploy.sh` ([ADR-0005](0005-git-pull-deploy.md)), so it
  cannot be the step that gets forgotten.
- Writing plain SQL keeps the schema comprehensible without a framework's abstractions in the
  way — which matters when returning to it after a gap.

### Negative / accepted costs

- WAL adds `-wal` and `-shm` files beside the database. Both matter: copying only the `.db` file
  can produce a torn backup, which is why [ADR-0011](0011-backup-policy.md) uses `.backup`
  rather than `cp`, and why all three are in `.gitignore`.
- Forward-only migrations mean no rollback. For a solo project with backups, correcting forward
  is simpler than maintaining reversals that will never be exercised.
- Hand-written SQL means no automatic schema generation from models, so the schema and any
  Python representation of it must be kept in step by hand.
- SQLite's `ALTER TABLE` is limited. Some changes need the create-copy-drop-rename dance written
  out by hand. Rare, and unpleasant when it happens.
- Still one writer at a time. WAL removes reader-writer contention, not writer-writer.

## Alternatives considered

- **Default journal mode.** No extra files, and readers and writers block each other. No reason
  to accept that.
- **Alembic.** Real migration tooling with autogeneration and downgrades, and it presumes
  SQLAlchemy and brings machinery disproportionate to a schema of a dozen tables.
- **Recreating the database from a schema file** and copying data across. Fine until there is
  production data worth keeping, which is from Sprint 03 onwards.
