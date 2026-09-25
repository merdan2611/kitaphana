# ADR-0019: Host on a single DigitalOcean droplet

- **Status**: Accepted
- **Date**: 2026-09-25
- **Supersedes**: [ADR-0015](0015-turkmentelecom-vds-hosting.md)

## Context

[ADR-0015](0015-turkmentelecom-vds-hosting.md) chose a Turkmentelecom VDS for the shortest
network path to readers in Turkmenistan. Five days on, that server still has no purchase date,
and Sprint 02 — the real domain, TLS and a public URL — has been blocked on it the whole time.
Sprints 01 and 03-06 have shipped on localhost ([ADR-0017](0017-local-dev-with-placeholder-fixtures.md)),
so the gap between what works and what anyone can actually use keeps growing.

A DigitalOcean droplet can be bought today, paid with the card already available, and created
with an SSH key in minutes.

## Decision

Host on **one DigitalOcean Basic droplet with 2 GB of RAM**, running Ubuntu LTS, in the
**Frankfurt region (FRA1)** — of DigitalOcean's regions, the one with the most direct route
towards Central Asia. At the time of writing the 2 GB / 1 vCPU size comes with a 50 GB SSD and
2 TB of monthly transfer for about $12 a month; check the current figures when buying.

Everything else stays as it was: one server running the application, nginx, the database and
the PDFs. Logging in is by SSH key only, the key added when the droplet is created.

The 2 GB of RAM is kept deliberately. Most of the other ADRs — SQLite
([ADR-0001](0001-fastapi-and-sqlite.md)), no Docker ([ADR-0004](0004-systemd-and-nginx-no-docker.md)),
no frontend build ([ADR-0003](0003-no-frontend-framework.md)), nginx sending the files
([ADR-0014](0014-x-accel-redirect-for-downloads.md)) — are sized to it, and none of them needs
reopening.

## Consequences

### Positive

- **Sprint 02 is unblocked now**, and the six sprints of localhost-only code finally meet a real
  server, real TLS and real latency.
- Snapshots, optional paid backups, a cloud firewall and resizing are all in the control panel,
  and documented. The unknown in R1 about what the provider offers mostly goes away.
- Resizing up is a button press, and a snapshot can recreate the whole server in another region
  if Frankfurt turns out to be the wrong choice.
- The stack does not care where it runs. Moving to a local server later means replaying the
  Sprint 02 notes on another machine, not rewriting anything.

### Negative / accepted costs

- **The server is outside Turkmenistan**, which is exactly what ADR-0015 was avoiding.
  International bandwidth into the country is limited, so pages and above all large downloads
  will be slower for the readers than a local server would have made them. Accepted for now in
  exchange for being online at all. Measure it in Sprint 02 rather than guess.
- **Reachability from inside Turkmenistan is not guaranteed.** Foreign cloud address ranges can
  be filtered. This joins R4 in [`../04-risks-and-research.md`](../04-risks-and-research.md) and
  has to be answered in Sprint 02 before anything else is built on top.
- **Less disk.** 50 GB instead of 120 GB. That is plenty for Phase 1 and 2, but the ~30 GB
  collection in Phase 3 plus growth could outrun it. The remedy is a DigitalOcean Block Storage
  volume mounted as `MEDIA_DIR`, or a larger droplet — decided with R6's answer, before the import,
  not during it. The "120 GB is a hard ceiling" in [ADR-0002](0002-local-disk-pdf-storage.md)
  now reads as "the droplet's disk is a ceiling until a volume is added".
- **Paid in US dollars with a foreign card**, every month. If the card stops working, the server
  stops with it.
- **Transfer is metered.** 2 TB a month is roughly 25,000 downloads of an 80 MB book, far beyond
  Phase 1, but it is a number to watch once the real collection is live.
- Still **a single point of failure**, as in ADR-0015. The mitigation is still being able to
  rebuild, and backups kept off the server ([ADR-0011](0011-backup-policy.md)).

## Alternatives considered

- **Keep waiting for the Turkmentelecom VDS.** Still the better network path for readers, but
  with no purchase date it leaves the project with no public URL indefinitely. Worth revisiting
  once it can actually be bought.
- **Hetzner or Contabo.** More RAM and disk per dollar, but no region closer to Turkmenistan
  than Frankfurt, and DigitalOcean's snapshots, documentation and firewall are the better fit
  for someone learning server administration in this very sprint.
- **A 1 GB droplet** to save money. Too little: cover rendering with `pdftoppm`, uvicorn and
  nginx together would sit near the limit, and every other decision assumes 2 GB.
- **DigitalOcean App Platform or another managed platform.** No local disk for the PDFs, no
  nginx `X-Accel-Redirect`, and it would reopen several settled ADRs at once.
