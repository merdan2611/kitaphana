# Sprint 06 — Stars and downloads

| | |
|---|---|
| **Status** | ⚪ Pending |
| **Phase** | 1 (usable library, codes on screen) |
| **Milestone** | M6 — I can download a book |
| **Estimated time** | ~1-2 weeks |
| **Depends on** | Sprint 05 |

## Goal

Close the loop: a reader with stars downloads a book, the ledger records it, and nginx sends the
file. This is the sprint the whole product is for, and the one where being sloppy is most
expensive — stars become real money in Phase 2, and the ledger written here is what will answer
every dispute afterwards.

Stars are granted by an admin in this phase. Buying them is Phase 2.

## You can now…

…be given ten stars, download a book that costs three, and see seven left with a record of
where the other three went.

## Tasks

### 1. Ledger schema

`migrations/004-stars.sql` creating `star_ledger`: id, user_id, amount (signed), reason
(`grant` / `topup` / `spend` / `refund`), reference (book id, payment id, request id),
note, created_at. Indexed on user_id.

**Append-only** ([ADR-0007](../adr/0007-star-credits-append-only-ledger.md)). Nothing in the
codebase ever updates or deletes a row here.

**Done when:** the migration applies and the column meanings are documented in the migration
file itself, where whoever reads the schema will find them.

### 2. The one function that writes to the ledger

A single `append_entry(...)` that every star movement goes through, and a `balance(user_id)`
that sums the rows. No other code touches the table. Put the rule in a comment at the top of the
module — this is the invariant the whole design rests on.

**Done when:** a grep for the table name outside this module finds nothing but the migration and
read-only reporting queries.

### 3. Admin grants

An admin page to grant stars to a reader found by phone number, with a required note explaining
why. Negative grants are allowed for corrections — as a new row, never an edit.

**Done when:** granting stars from the admin panel changes the reader's balance and leaves a row
with the admin's note attached.

### 4. Balance on screen

The balance in the header for signed-in readers, and a history page on the account listing every
entry with its reason and date. Readers should be able to see exactly what happened to their
stars without asking.

**Done when:** the header balance matches the sum of the history page, on a fresh account and on
one with a dozen entries.

### 5. The download endpoint

The core of the sprint:

1. Require a session; anonymous visitors are sent to sign in.
2. Load the book. Unpublished means 404.
3. If the price is zero, skip to step 5.
4. **In one transaction:** read the balance, refuse if it is insufficient, and append the
   `spend` row. Reading and writing must be in the same transaction, or two downloads started
   at the same moment can both pass a check only one should have passed.
5. Return an empty response with `X-Accel-Redirect` pointing at the file and
   `Content-Disposition` giving a filename built from the book's title, not its hash
   ([ADR-0014](../adr/0014-x-accel-redirect-for-downloads.md)).

**Done when:** a download deducts exactly once, and two simultaneous downloads with only enough
stars for one result in one success and one refusal — never two successes.

### 6. Local development fallback

`X-Accel-Redirect` means nothing without nginx, so under a bare `uvicorn` the endpoint must
stream the file directly instead. One branch on a setting, with the direct path used only in
development.

**Done when:** downloads work locally and on the server, and the branch is exercised both ways
at least once by hand.

### 7. When a reader cannot afford it

A page explaining the price, the current balance, and how to get more stars — which in Phase 1
means asking the admin, stated plainly rather than pointing at a purchase page that does not
exist.

**Done when:** an under-funded download explains itself instead of failing.

### 8. Download rate limit

A per-account limit on downloads per hour and per day. Stars already make bulk downloading
expensive, but a limit costs nothing to add and covers the case of a free-book sweep.

**Done when:** exceeding the limit is refused with a clear message, and free books are limited
too.

## Done when (sprint acceptance)

- [ ] A reader with stars downloads a priced book and the balance falls by exactly the price.
- [ ] A reader without enough stars is refused, with an explanation.
- [ ] Free books download for any signed-in reader and still write a zero-amount ledger row, so
      the download is recorded.
- [ ] Concurrent downloads cannot overdraw a balance.
- [ ] nginx serves the bytes: the uvicorn worker is free within milliseconds.
- [ ] The media directory is not reachable by direct URL.
- [ ] The history page accounts for every star the reader has ever had.
- [ ] Verified end-to-end on localhost, including the direct-serve fallback for downloads —
      and will be exercised for real, over mobile data with pausing and resuming, once deployed
      in Sprint 02's catch-up pass (see
      [ADR-0017](../adr/0017-local-dev-with-placeholder-fixtures.md)).

## Tests

The most important tests in the project.

- Balance is the sum of entries: after a grant, a spend and a refund, the arithmetic is right.
- A spend with an insufficient balance is refused and writes **no** row.
- Concurrency: two simultaneous downloads with stars for one produce exactly one spend row.
- A free book writes a zero-amount row and always succeeds.
- Anonymous download attempts redirect to sign-in and write nothing.
- An unpublished book's download URL returns 404.
- The response carries `X-Accel-Redirect` in production mode and real bytes in development mode.
- `Content-Disposition` contains a readable title, correctly encoded for non-ASCII characters —
  Turkmen titles will exercise this.
- Download rate limits fire.

Manually, once nginx exists locally or on the server: start a large download, watch
`systemctl status kitaphana` (or the local process) to confirm the worker is idle while the
transfer continues, then kill the download at 50% and resume it. If nginx is not set up locally
yet, this check waits for Sprint 02's catch-up pass — the direct-serve fallback path is what
gets exercised on localhost until then.

## Files this sprint creates / touches

`app/stars.py` · `app/downloads.py` · `migrations/004-stars.sql` ·
`templates/account_history.html` · `templates/insufficient_stars.html` ·
`templates/admin/grant.html` · `templates/book.html` · `tests/test_stars.py` ·
`tests/test_downloads.py`

## No-gos

- No buying stars. No payment webhook, no packages, no prices in TMT — all Phase 2.
- No cached balance column. The ledger is the source of truth; optimise only if it is ever
  measurably slow, which it will not be.
- No gifting stars between readers, no referral bonuses, no promotions.
- No expiring stars.
- No download resumption logic of your own — nginx already does it correctly.

## References

[ADR-0007](../adr/0007-star-credits-append-only-ledger.md) ·
[ADR-0014](../adr/0014-x-accel-redirect-for-downloads.md) ·
[ADR-0002](../adr/0002-local-disk-pdf-storage.md) ·
[ADR-0017](../adr/0017-local-dev-with-placeholder-fixtures.md)
