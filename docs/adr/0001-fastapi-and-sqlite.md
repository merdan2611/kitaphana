# ADR-0001: FastAPI and SQLite for backend and database

- **Status**: Accepted
- **Date**: 2026-09-20

## Context

Kitaphana is built by one developer with five to ten hours a week, on a server with 2 vCPU and
2 GB of RAM. The workload is almost entirely reads: browsing a catalogue and downloading files.
Writes are rare and small — an account, a ledger entry, a request, an upvote. There is no
expectation of concurrent write pressure, and if it ever arrives, it will arrive slowly enough
to see coming.

## Decision

The backend is **FastAPI** on Python 3.11 or newer. The database is **SQLite**, one file on
local disk, accessed directly rather than through an ORM-heavy stack.

## Consequences

### Positive

- The database is a file. Backing it up is copying it; inspecting it is one command; moving the
  whole application to another machine is `scp`. On a project whose disaster recovery plan is
  "rebuild it by hand", that is worth a great deal.
- No database server process, so no second thing to configure, secure, keep patched, or lose
  200 MB of RAM to.
- FastAPI's request validation catches malformed input at the edge, which on a project with no
  second reviewer is genuine protection.
- Python is the language the developer already knows. The scarce resource here is hours, not
  runtime performance.

### Negative / accepted costs

- SQLite allows one writer at a time. Under concurrent writes, others wait, and past a timeout
  they fail. At this scale that is invisible; it would not be at a hundred times this scale.
- No connection from another machine, so no separate analytics or admin process reaching into
  the database over a network. Everything runs on the one box.
- Some Python async footguns: SQLite calls are blocking, so they must not be made naively from
  an async endpoint on the event loop. Use synchronous route handlers, or run database work in
  a thread pool. This needs to be decided once in Sprint 01 and then followed.
- Moving to PostgreSQL later would be a real migration, not a configuration change.

## Alternatives considered

- **PostgreSQL.** The right answer at a larger scale and the wrong one here: several hundred
  megabytes of RAM on a 2 GB machine, another service to administer, and another thing to get
  wrong in backups — all to solve write concurrency the project does not have.
- **Django.** Brings an admin interface almost free, which is tempting given that an admin panel
  is needed from the start. Rejected because the rest of Django's weight is unwanted and its
  admin is difficult to shape into something a non-developer should ever see. A small hand-built
  admin is more work once, and less work every time after.
- **Go or Node.** Both would run in less memory. Neither is worth the hours lost to working in a
  less familiar language.
