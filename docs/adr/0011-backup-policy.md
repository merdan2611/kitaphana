# ADR-0011: Back up the database, not the PDFs

- **Status**: Accepted
- **Date**: 2026-09-20

## Context

The original plan for this project was to have no backups at all. The reasoning was sound as far
as it went: the PDFs are large, they are already on the developer's own machine and external
drive, and if the server were lost they could simply be uploaded again. Backing up 30 GB of
files that already exist in two other places is paying to store a third copy of something not at
risk.

The reasoning covers the PDFs. It does not cover the database, and the difference matters more
than it first appears. `kitaphana.db` holds every account, every request and upvote, and the
entire star ledger — including stars people have **paid money for**. Unlike the PDFs, that data
exists in exactly one place. If the disk fails, it is not restored by re-uploading anything: it
is gone, and the project's obligations to people who paid go with it.

The two kinds of data have opposite properties, so they get opposite policies.

## Decision

**PDFs are not backed up.** The originals stay on the developer's machine and external drive.
Recovery after a total loss is re-uploading them, which is slow and entirely survivable.

**The database is backed up, nightly and off the server:**

- A nightly cron job runs `sqlite3 kitaphana.db ".backup /path/backups/kitaphana-$(date +%F).db"`.
  The `.backup` command is used specifically because copying a live SQLite file with `cp` can
  capture a torn database, particularly in WAL mode ([ADR-0016](0016-sqlite-wal-and-migrations.md)).
- Backups are pruned to a rolling window so they cannot fill the disk.
- They are **pulled down to the developer's machine periodically**. A backup that only exists on
  the server it is protecting is not a backup.
- **At least one restore is performed before Phase 1 ends**, in Sprint 08. An untested backup is
  an assumption, not a safeguard.

## Consequences

### Positive

- The irreplaceable data — accounts and paid balances — is protected, at a cost of a few
  megabytes and one cron entry.
- Restoring is copying a file back and restarting the service.
- The rehearsed restore means the procedure is known before it is needed at the worst possible
  moment.

### Negative / accepted costs

- Losing the server still means re-uploading the whole collection over a slow link, which is
  days of elapsed time. Accepted; the alternative was paying for off-site storage of 30 GB
  ([ADR-0002](0002-local-disk-pdf-storage.md)).
- Up to 24 hours of database changes can be lost between nightly backups. Acceptable at this
  volume, and reducible later by running more often.
- Pulling backups down is a manual habit, and habits lapse. Better than nothing, and worth
  automating from the developer's side once the pattern settles.
- A restored database can reference PDFs that are not back on disk yet, so the catalogue will
  show books that cannot be downloaded until the re-upload finishes. Worth handling gracefully
  rather than with a stack trace.

## Alternatives considered

- **No backups at all**, as originally planned. Correct for the PDFs and unacceptable for the
  ledger, which is what this ADR changes.
- **VDS provider snapshots.** Possibly the simplest option if the panel offers them — R1 in
  [`../04-risks-and-research.md`](../04-risks-and-research.md). They would complement this
  policy rather than replace it: a snapshot at the same provider does not protect against losing
  the account.
- **Off-site backup of everything including PDFs.** The thorough answer, needing foreign storage
  and 30 GB of upload, and solving a problem the external drive already solves.
