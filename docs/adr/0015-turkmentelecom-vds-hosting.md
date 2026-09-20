# ADR-0015: Host on a single Turkmentelecom VDS

- **Status**: Accepted
- **Date**: 2026-09-20

## Context

The readers are in Turkmenistan. International bandwidth in and out of the country is limited
and slow, so a server hosted abroad would be slow for exactly the people the library is for —
and it is serving large files, where that penalty is paid most heavily.

Foreign hosting also has to be paid for with a foreign card in a foreign currency, which is an
obstacle in its own right.

## Decision

Host on a **Turkmentelecom VDS, Storage M plan**: 2 vCPU, 2 GB RAM, 120 GB SSD, at 403.20 TMT
per month. One server, running everything — the application, nginx, the database, and the PDFs.

## Consequences

### Positive

- The shortest network path to the readers, which is what makes downloading an 80 MB book
  tolerable.
- Paid locally in local currency, with local support.
- 120 GB of SSD is generous relative to the plan's price and fits the known collection with
  headroom.
- Everything on one machine means no inter-service network to configure or secure.

### Negative / accepted costs

- **2 GB of RAM constrains every other decision in this project**, and most of the other ADRs
  are downstream of it: SQLite rather than PostgreSQL ([ADR-0001](0001-fastapi-and-sqlite.md)),
  no Docker ([ADR-0004](0004-systemd-and-nginx-no-docker.md)), no frontend build
  ([ADR-0003](0003-no-frontend-framework.md)), and nginx rather than Python serving files
  ([ADR-0014](0014-x-accel-redirect-for-downloads.md)).
- **A single point of failure.** If the server is down, the library is down; if the disk fails,
  the database goes with it unless it has been backed up ([ADR-0011](0011-backup-policy.md)).
  This is accepted, not solved. The mitigation is being able to rebuild, not being redundant.
- Reaching the site from outside Turkmenistan will be slower — the inverse of the advantage, and
  the right trade for this audience.
- Whatever the provider's control panel offers for snapshots and support is unknown — R1 in
  [`../04-risks-and-research.md`](../04-risks-and-research.md).
- Scaling means a bigger plan from the same provider. There is no horizontal path from here
  without revisiting most of the stack.

## Alternatives considered

- **A foreign VPS** (Hetzner, DigitalOcean, Contabo). Cheaper per gigabyte of RAM, better
  tooling, and slow for the readers and awkward to pay for. The audience decides this one.
- **Two servers**, separating application and files. Removes the single point of failure only
  partly, doubles the cost, and adds a network hop for every download.
- **A smaller plan** to save money. The disk is the binding constraint, and Storage M is chosen
  for the 120 GB rather than the CPU.
