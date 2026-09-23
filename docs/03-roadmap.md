# Roadmap

**The "where am I?" file. Open this first in every session.**

Sprints 01 and 03-06 have shipped: anyone can browse and search the library, an admin can add
books and grant stars, and a signed-in reader can spend stars to download a book. Sprint 07 —
Requests is next; Sprint 02 still waits for the VDS.

## Current sprint

| | |
|---|---|
| **Sprint** | S07 — Requests |
| **Status** | ⚪ Pending |
| **Started** | — |
| **Phase** | 1 (usable library, codes on screen) |
| **Sprint doc** | [`sprints/sprint-07-requests.md`](sprints/sprint-07-requests.md) |
| **Milestone** | M7 — I can ask for a book |
| **Next up** | S08 — Beta hardening (S02 runs whenever the VDS is available — see [ADR-0017](adr/0017-local-dev-with-placeholder-fixtures.md)) |

## Phase 1 sprints

⚪ Pending · 🟡 In progress · 🟢 Shipped · 🔴 Blocked

| # | Sprint | Status | Shipped | Milestone | You can now… |
|---|---|---|---|---|---|
| 01 | [Foundations](sprints/sprint-01-foundations.md) | 🟢 Shipped | 2026-09-21 | M1 | …run the app locally and see a page |
| 02 | [Production ground](sprints/sprint-02-production-ground.md) | 🔴 Blocked — VDS not yet purchased | — | M2 | …open the real domain over HTTPS |
| 03 | [Accounts](sprints/sprint-03-accounts.md) | 🟢 Shipped | 2026-09-23 | M3 | …sign up with a phone number and stay logged in |
| 04 | [Admin and ingest](sprints/sprint-04-admin-and-ingest.md) | 🟢 Shipped | 2026-09-23 | M4 | …put a book into the library |
| 05 | [Public catalogue](sprints/sprint-05-public-catalogue.md) | 🟢 Shipped | 2026-09-23 | M5 | …find that book by searching |
| 06 | [Stars and downloads](sprints/sprint-06-stars-and-downloads.md) | 🟢 Shipped | 2026-09-23 | M6 | …spend stars and get the PDF |
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

- **2026-09-23** — Sprint 06 (Stars and downloads) shipped. An admin can give a reader stars by
  phone number, with a note the reader also sees, and correct a mistake with a negative entry.
  A signed-in reader sees their balance in the header, downloads a free book for nothing or a
  priced one for exactly its price, and gets a PDF named after the book («Älem.pdf»), not its
  hash. A book paid for once downloads again for free. Without enough stars, a page explains
  the price, the balance and that stars come from the admin, and nothing is charged. The
  history page lists every star movement with the balance after each. Every movement is a row
  in an append-only ledger that the database itself refuses to edit or delete; simultaneous
  downloads cannot overdraw a balance or charge twice; downloads are limited to 10 an hour and
  30 a day. nginx sending the bytes is ready in the app and waits for Sprint 02 to be checked
  for real; under a bare uvicorn the app sends the file itself.

- **2026-09-23** — Sprint 05 (Public catalogue) shipped. Anyone, signed in or not, can browse the
  published books, filter by language, sort newest-first or by title, and search by title or
  author. Search ignores case and Turkmen letters, so "alem" finds «Älem» and works without a
  Turkmen keyboard, and it stays around 20 ms with 30,000 books. Each book has its own page with
  cover, details and description. Visitors are invited to log in and are brought back to the
  book afterwards; signed-in readers see the download button that Sprint 06 will switch on.
  Unknown, unpublished and malformed addresses all get a real 404 page. On phones the catalogue
  is a list with a Katalog tab; on the website it is a cover grid.

- **2026-09-23** — Between sprints: the site became responsive in earnest. On desktop it is a
  website (top navigation, wide pages, two columns where they help); on a phone it feels like an
  app (top bar and a bottom tab bar), all in the browser and not installable
  ([ADR-0018](adr/0018-responsive-website-and-phone-layout.md)). Colours are now classic and
  neutral, each one a single variable so they can be changed one at a time.

- **2026-09-23** — Sprint 04 (Admin and ingest) shipped. An admin uploads a PDF from the
  browser with a progress bar. It is stored by SHA-256 under a fanned-out path, gets a cover
  rendered from its first page, and lands as an unpublished draft with title and author taken
  from the file's own metadata. The same file uploaded twice is refused, naming the book it
  duplicates. Books can be searched, edited, priced, published, given a new cover, and deleted
  after a confirmation. `python -m scripts.seed_fixtures` loads five public-domain books through
  the same path and refuses to touch a database holding real books. Server memory stays flat
  during a 150 MB upload. The public pages and the admin got their first real design.

- **2026-09-23** — Sprint 03 (Accounts) shipped. You can sign up or log in with a Turkmen phone
  number typed any common way, get a six-digit code on screen, and stay logged in across browser
  restarts for 180 days. Wrong codes burn after five tries, code requests are rate-limited per
  number and per address, and codes and session tokens are only stored hashed. A loud banner
  marks dev-OTP mode on every page. `python -m scripts.make_admin` sets the admin flag that
  Sprint 04's pages will check.

- **2026-09-21** — Sprint 01 (Foundations) shipped. `uvicorn app.main:app` serves a home page
  through the real base layout, `GET /health` reports the applied migration number, and SQLite
  runs in WAL mode with foreign keys enforced and a forward-only migration runner
  (`python -m scripts.migrate`, safe to run twice).
- **2026-09-20** — Repository created; documentation, ADRs and Phase 1 sprint plans written.
