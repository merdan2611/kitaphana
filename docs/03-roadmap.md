# Roadmap

**The "where am I?" file. Open this first in every session.**

Sprint 01 has shipped: the skeleton runs locally. Sprint 03 — Accounts is next.

## Current sprint

| | |
|---|---|
| **Sprint** | S03 — Accounts |
| **Status** | ⚪ Pending |
| **Started** | — |
| **Phase** | 1 (usable library, codes on screen) |
| **Sprint doc** | [`sprints/sprint-03-accounts.md`](sprints/sprint-03-accounts.md) |
| **Milestone** | M3 — I can log in |
| **Next up** | S04 — Admin and ingest (S02 runs whenever the VDS is available — see [ADR-0017](adr/0017-local-dev-with-placeholder-fixtures.md)) |

## Phase 1 sprints

⚪ Pending · 🟡 In progress · 🟢 Shipped · 🔴 Blocked

| # | Sprint | Status | Shipped | Milestone | You can now… |
|---|---|---|---|---|---|
| 01 | [Foundations](sprints/sprint-01-foundations.md) | 🟢 Shipped | 2026-09-21 | M1 | …run the app locally and see a page |
| 02 | [Production ground](sprints/sprint-02-production-ground.md) | 🔴 Blocked — VDS not yet purchased | — | M2 | …open the real domain over HTTPS |
| 03 | [Accounts](sprints/sprint-03-accounts.md) | ⚪ Pending | — | M3 | …sign up with a phone number and stay logged in |
| 04 | [Admin and ingest](sprints/sprint-04-admin-and-ingest.md) | ⚪ Pending | — | M4 | …put a book into the library |
| 05 | [Public catalogue](sprints/sprint-05-public-catalogue.md) | ⚪ Pending | — | M5 | …find that book by searching |
| 06 | [Stars and downloads](sprints/sprint-06-stars-and-downloads.md) | ⚪ Pending | — | M6 | …spend stars and get the PDF |
| 07 | [Requests](sprints/sprint-07-requests.md) | ⚪ Pending | — | M7 | …ask for a missing book and upvote others |
| 08 | [Beta hardening](sprints/sprint-08-beta-hardening.md) | ⚪ Pending | — | M8 | …hand the link to a tester without apologising |

## Milestones

| | Milestone | Reached when |
|---|---|---|
| M1 | It runs on my machine | `uvicorn` serves a page backed by the real schema |
| M2 | It is on the internet | The domain resolves, HTTPS works, systemd restarts it after reboot |
| M3 | I can log in | Phone plus on-screen code creates a session that survives a browser restart |
| M4 | I can put a book in | Admin uploads a PDF with metadata; duplicates are rejected |
| M5 | I can find a book | Catalogue and search work on a phone-sized screen |
| M6 | I can download a book | Stars are checked, the ledger is written, nginx sends the file |
| M7 | I can ask for a book | Requests are posted anonymously and upvoted |
| M8 | Testers can use it | Backups run, errors are logged, and real people complete the loop |

## Order and dependencies

```
S01 ──┬──► S03 ──┬──► S04 ──► S05 ──► S06 ──┐
      │          │                          ├──► S08
      │          └──────────► S07 ──────────┘
      └──► S02 (needs the VDS — run as soon as it exists; not on this critical path)
```

- **S02 no longer gates S03-S07.** The original plan deployed second so the least familiar work
  happened early; that is still the right move the moment the VDS exists, but it does not exist
  yet and has no purchase date. Sprints 01 and 03-07 are built and fully tested on localhost with
  placeholder content in the meantime, and S02 runs whenever it can, independent of sprint order.
  See [ADR-0017](adr/0017-local-dev-with-placeholder-fixtures.md).
- **S03 gates S04-S07** — admin authentication is built on the same session machinery as
  reader authentication.
- **S06 needs S05**, because a download button has to live on a book page.
- **S07 needs S04**, because fulfilling a request means linking it to a book, but it does not
  need stars and can be moved earlier if the star work stalls.

## How to update this file

At the **end** of a sprint, not the beginning:

1. Set that sprint's row to 🟢 Shipped and fill in the date.
2. Add a line to the shipped log below, saying what a person can now do — not what was coded.
3. Move the current-sprint block to the next sprint and set it to 🟡 In progress when you
   start it.
4. If the sprint changed the plan — and it will — edit the affected sprint documents now,
   while you still remember why. A roadmap that describes an intention nobody holds any more
   is worse than no roadmap.

If a sprint is 🔴 Blocked, say what it is blocked on in the status cell and open an entry in
[`04-risks-and-research.md`](04-risks-and-research.md).

## Shipped log

*Newest first.*

- **2026-09-21** — Sprint 01 (Foundations) shipped. `uvicorn app.main:app` serves a home page
  through the real base layout, `GET /health` reports the applied migration number, and SQLite
  runs in WAL mode with foreign keys enforced and a forward-only migration runner
  (`python -m scripts.migrate`, safe to run twice).
- **2026-09-20** — Repository created; documentation, ADRs and Phase 1 sprint plans written.
