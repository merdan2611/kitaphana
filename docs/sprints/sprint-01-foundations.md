# Sprint 01 — Foundations

| | |
|---|---|
| **Status** | ⚪ Pending |
| **Phase** | 1 (usable library, codes on screen) |
| **Milestone** | M1 — It runs on my machine |
| **Estimated time** | ~1 week (5-10 hours) |
| **Depends on** | Nothing |

## Goal

Put down the skeleton everything else is built on: a FastAPI application that starts, a SQLite
database configured the way [ADR-0016](../adr/0016-sqlite-wal-and-migrations.md) requires, a
migration mechanism, and one page that renders through the real template layout.

Nothing here is user-facing value. It is the sprint that makes the next seven cheap.

## You can now…

…clone the repository onto a machine that has never seen it, follow the README, and have the
library's home page open in a browser three minutes later.

## Tasks

### 1. Project skeleton

Create `app/` (with `main.py`, `config.py`, `db.py`), `templates/`, `static/`, `migrations/`,
`requirements.txt` and `.env.example`. Pin dependencies to exact versions — the server will
install from this file months from now and should get the same thing.

**Done when:** `pip install -r requirements.txt` in a fresh virtual environment succeeds, and
`uvicorn app.main:app` starts without error.

### 2. Configuration from the environment

A `config.py` that reads settings once at startup: database path, media directory, secret key,
dev-OTP flag, debug flag. Every setting has a safe default, and **the dev-OTP flag defaults to
off** ([ADR-0013](../adr/0013-dev-otp-mode.md)). `.env.example` documents each one; `.env` is
git-ignored.

**Done when:** running with no `.env` at all starts in a safe default configuration, and a
setting changed in `.env` visibly takes effect.

### 3. Database connection

A `db.py` that opens SQLite and, on every connection, sets `journal_mode=WAL`,
`foreign_keys=ON`, and a `busy_timeout` of a few seconds. Decide here — once, for the whole
project — how blocking SQLite calls are kept off the async event loop, and write the reason in a
comment.

**Done when:** `PRAGMA journal_mode` returns `wal` and `PRAGMA foreign_keys` returns `1` on a
connection taken from the application, and `kitaphana.db-wal` appears on disk after a write.

### 4. Migration runner

A script that finds `migrations/*.sql`, applies in filename order any that are not recorded in
`schema_migrations`, and records each one it applies. Forward-only, and it must be safe to run
twice.

**Done when:** running it on an empty directory creates the database; running it again applies
nothing and exits cleanly.

### 5. Initial schema

`migrations/001-initial.sql` creating the two spine tables:

- `users` — id, phone (unique, normalised `+993…`), created_at, is_admin, is_blocked
- `books` — id, title, author, year, language, description, content_hash (unique), file_size,
  page_count, cover_path, price_stars, is_published, created_at

Later sprints add their own tables in their own migrations rather than editing this one.

**Done when:** both tables exist with their constraints, and inserting a duplicate phone or
duplicate content hash is rejected by the database itself rather than by application code.

### 6. Base layout and stylesheet

`templates/base.html` with header, navigation, footer and a content block, plus one
`static/style.css`. Mobile-first: write the narrow layout first and widen it, rather than the
reverse ([ADR-0003](../adr/0003-no-frontend-framework.md)). Interface strings are in Turkmen.

**Done when:** the page is legible and correctly laid out at 360 px wide, and the stylesheet is
the only one the page loads.

### 7. Home page and health endpoint

A home page extending the base layout, and `GET /health` returning JSON with status, the applied
migration number, and the application version. Sprint 02 needs `/health` to prove a deployment
worked.

**Done when:** the home page renders through the layout, and `/health` returns HTTP 200 with the
current migration number.

## Done when (sprint acceptance)

- [ ] A fresh clone reaches a rendered home page by following the README alone, with no
      undocumented step.
- [ ] `/health` returns 200 and reports the right migration number.
- [ ] The database is in WAL mode with foreign keys enforced.
- [ ] Running the migration runner twice in a row is harmless.
- [ ] Nothing secret is committed: `git status` is clean and `.env` and `*.db` are ignored.

## Tests

The testing approach for the whole project starts here, and it is deliberately small: test the
things that are quietly wrong rather than obviously broken. A page that fails to render is
noticed immediately; a phone number normalised two different ways is not.

- Set up `pytest` and FastAPI's `TestClient` against a temporary database.
- `GET /health` returns 200 with the expected shape.
- The migration runner applies a fresh database, then is a no-op on the second run.
- A connection from the application reports WAL mode and foreign key enforcement.

**Done when:** `pytest` runs green from a clean checkout and the command is in the README.

## Files this sprint creates

`requirements.txt` · `.env.example` · `app/{main,config,db}.py` · `migrations/001-initial.sql`
· `scripts/migrate.py` · `templates/base.html` · `templates/index.html` · `static/style.css` ·
`tests/`

## No-gos

- No authentication — that is Sprint 03.
- No file uploads, no book pages, no admin.
- No Docker, no build step, no CSS framework, no JavaScript framework.
- No design polish. The layout needs to be correct, not finished.
- No deployment. It runs locally only; Sprint 02 puts it on the server.

## References

[ADR-0001](../adr/0001-fastapi-and-sqlite.md) ·
[ADR-0003](../adr/0003-no-frontend-framework.md) ·
[ADR-0013](../adr/0013-dev-otp-mode.md) ·
[ADR-0016](../adr/0016-sqlite-wal-and-migrations.md)
