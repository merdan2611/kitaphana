# Architecture Decision Records

One decision per file, with the reasoning that produced it. The point is not ceremony — it is
that in four months, when something is annoying, this folder says whether it is annoying
because it was a mistake or annoying because it was the price of something that mattered.

## Rules

- Numbered sequentially, four digits, never reused and never renumbered.
- **Immutable once accepted.** A decision that changes gets a *new* ADR that supersedes the
  old one; the old one stays, with its status changed to `Superseded by ADR-XXXX`. The history
  of what was believed is the useful part.
- One decision per record. If it needs "and", it is probably two records.
- Concrete, not aspirational. Write what was done and why, not what would be nice.

## Format

```markdown
# ADR-NNNN: Title

- **Status**: Accepted | Superseded by ADR-XXXX | Rejected
- **Date**: YYYY-MM-DD

## Context
## Decision
## Consequences
### Positive
### Negative / accepted costs
## Alternatives considered
```

## Index

| # | Title | Status | Date |
|---|---|---|---|
| [0001](0001-fastapi-and-sqlite.md) | FastAPI and SQLite for backend and database | Accepted | 2026-09-20 |
| [0002](0002-local-disk-pdf-storage.md) | Store PDFs on the server's local disk | Accepted | 2026-09-20 |
| [0003](0003-no-frontend-framework.md) | Server-rendered HTML, no frontend framework | Accepted | 2026-09-20 |
| [0004](0004-systemd-and-nginx-no-docker.md) | Run under systemd behind nginx, without Docker | Accepted | 2026-09-20 |
| [0005](0005-git-pull-deploy.md) | Deploy by pulling git on the server | Accepted | 2026-09-20 |
| [0006](0006-phone-number-and-otp-auth.md) | Accounts are a phone number and an SMS code | Accepted | 2026-09-20 |
| [0007](0007-star-credits-append-only-ledger.md) | Star balances derive from an append-only ledger | Accepted | 2026-09-20 |
| [0008](0008-sms-forwarding-payment-detection.md) | Detect payments with a forwarding phone and a webhook | Accepted | 2026-09-20 |
| [0009](0009-anonymous-requests-with-upvotes.md) | Book requests are anonymous and publicly upvoted | Accepted | 2026-09-20 |
| [0010](0010-semi-automatic-bulk-import.md) | Bulk import is semi-automatic, with a manual queue | Accepted | 2026-09-20 |
| [0011](0011-backup-policy.md) | Back up the database, not the PDFs | Accepted | 2026-09-20 |
| [0012](0012-foreign-domain-registrar.md) | Register the domain with a foreign registrar | Accepted | 2026-09-20 |
| [0013](0013-dev-otp-mode.md) | Ship Phase 1 with OTP codes shown on screen | Accepted | 2026-09-20 |
| [0014](0014-x-accel-redirect-for-downloads.md) | Serve downloads with nginx via X-Accel-Redirect | Accepted | 2026-09-20 |
| [0015](0015-turkmentelecom-vds-hosting.md) | Host on a single Turkmentelecom VDS | Superseded by 0019 | 2026-09-20 |
| [0016](0016-sqlite-wal-and-migrations.md) | SQLite in WAL mode with plain SQL migrations | Accepted | 2026-09-20 |
| [0017](0017-local-dev-with-placeholder-fixtures.md) | Develop locally with placeholder fixtures before the VDS is available | Accepted | 2026-09-21 |
| [0018](0018-responsive-website-and-phone-layout.md) | A website on wide screens, an app-style layout on phones | Accepted | 2026-09-23 |
| [0019](0019-digitalocean-droplet-hosting.md) | Host on a single DigitalOcean droplet | Accepted | 2026-09-25 |
