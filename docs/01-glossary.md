# Glossary

The vocabulary used across these documents, the database schema, and the code. Where a term
also appears in the interface, the Turkmen copy is given — those strings need a native pass
before they ship, and they are the only Turkmen in this documentation.

## People

| Term | Meaning |
|---|---|
| **Reader** | Someone with an account, identified solely by a phone number. The only kind of end user. |
| **Anonymous visitor** | Someone browsing without an account. Can search, browse and upvote; cannot download. |
| **Admin** | The developer. Adds books, fulfils requests, grants stars, sees the ledger. There is exactly one admin role and no permission tiers. |
| **Beta tester** | An invited reader during Phase 1, using the library while OTP codes still appear on screen. |

## Books

| Term | Meaning |
|---|---|
| **Book** | One catalogue entry: title, author, year, language, description, cover, and exactly one PDF. A second scan of the same work is a second book, not a second edition — there is no edition model. |
| **PDF** | The file itself, on the server's local disk, named by its content hash rather than its title. |
| **Content hash** | SHA-256 of the PDF bytes. Used to detect that a file is already in the library regardless of what it was called. |
| **Cover** | A single image for a book. Optional; the catalogue must look correct without one. |
| **Free book** | Costs zero stars to download. Still requires an account. |
| **Priced book** | Costs a set number of stars. The price is a per-book field, not a global constant. |
| **Catalogue** | The public, searchable list of books. |
| **Fixture / placeholder book** | A real public-domain text used to populate the catalogue during local development, kept under `fixtures/books/` and out of the production database. Stands in for the real collection until it is imported in Phase 3; never a substitute for real editorial judgement about what belongs in the library. See [ADR-0017](adr/0017-local-dev-with-placeholder-fixtures.md). |

## Stars

| Term | Meaning |
|---|---|
| **Star** | The unit of download credit. UI copy: *ýyldyz*. |
| **Ledger** | Append-only table of every star movement. Rows are never updated or deleted. |
| **Ledger entry** | One movement: who, how many stars (signed), why, and a reference to what caused it. |
| **Balance** | The sum of a reader's ledger entries. Derived, never stored as a mutable field. |
| **Grant** | Stars added by an admin by hand — a welcome bonus, a correction, an apology. |
| **Top-up** | Stars added because a payment arrived. Phase 2. |
| **Spend** | Stars removed by a download. Never positive, always references the book. Zero for a free book and for downloading again a book already paid for, so every download is recorded. |
| **Star package** | A fixed amount of TMT buying a fixed number of stars. Phase 2. |

## Requests

| Term | Meaning |
|---|---|
| **Request** | A reader asking for a book the library does not have. Published anonymously: the requester is stored so it cannot be spammed, but is never displayed. |
| **Upvote** | A signal that someone else wants that book too. One per reader per request. |
| **Fulfilment** | An admin linking a request to a newly added book, which closes it. |
| **Priority request** | Phase 4: spending stars to push a request up the queue. Does not exist yet. |

## Accounts

| Term | Meaning |
|---|---|
| **Phone number** | The account identifier. Stored in one normalised form: `+993XXXXXXXX`. |
| **OTP** | The one-time code proving the reader controls that phone number. Short-lived, single-use, rate-limited, stored hashed. |
| **Dev-OTP mode** | Phase 1 setting where the code is displayed in the browser instead of sent by SMS, so the whole site can be tested end to end before any SMS plumbing exists. Controlled by an environment variable, and it must be impossible to leave on by accident once real SMS works. |
| **Session** | A signed cookie identifying a logged-in reader. Long-lived: re-entering an SMS code often would be a real cost to users. |

## Payments (Phase 2)

| Term | Meaning |
|---|---|
| **Operator transfer** | A reader sending mobile credit from their phone to the project's number — the payment method. |
| **Forwarder phone** | A dedicated Android phone holding that number, running an app that posts every received SMS to the backend. |
| **SMS webhook** | The endpoint that phone posts to. Authenticated with a shared secret, and idempotent, because the same SMS will sometimes be delivered twice. |
| **Reconciliation** | Matching an incoming payment SMS to a reader by the sender's phone number, then writing a top-up entry. Anything that cannot be matched goes to a queue for the admin, never silently dropped. |

## Project and operations

| Term | Meaning |
|---|---|
| **Phase** | A block of work ending in something demonstrable. See [`02-phases.md`](02-phases.md). |
| **Sprint** | About a week at 5-10 hours. Has a task list, a definition of done, and a No-gos list. |
| **No-gos** | Explicitly out of scope for that sprint. The mechanism that stops scope creep. |
| **ADR** | Architecture Decision Record — one settled decision, with its reasoning, in [`adr/`](adr/). |
| **VDS** | The Turkmentelecom virtual server the whole thing runs on. 2 vCPU, 2 GB RAM, 120 GB SSD. |
| **Deploy** | `git pull` on the VDS followed by a systemd restart. Nothing is built on the server. |
| **X-Accel-Redirect** | The nginx header letting the app authorise a download while nginx sends the actual bytes. See [ADR-0014](adr/0014-x-accel-redirect-for-downloads.md). |
| **WAL** | SQLite's write-ahead logging mode, which lets reads continue during a write. On from the start. |
