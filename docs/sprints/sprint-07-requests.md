# Sprint 07 — Requests

| | |
|---|---|
| **Status** | 🟢 Shipped 2026-09-23 |
| **Phase** | 1 (usable library, codes on screen) |
| **Milestone** | M7 — I can ask for a book |
| **Estimated time** | ~1 week (5-10 hours) |
| **Depends on** | Sprint 04 (fulfilment links a request to a book) |

## Goal

Let readers say what the library is missing, and let everyone else agree. This is the cheapest
research the project will ever get: instead of guessing which books to digitise next, read the
list in upvote order.

It depends on Sprint 04 rather than Sprint 06 — fulfilment needs books, not stars — so it can be
brought forward if the star work stalls.

## You can now…

…ask for a book that is not in the library, and upvote somebody else's request.

## Tasks

> **Carried in from Sprint 05 (2026-09-23):** this sprint's migration is `006-requests.sql`
> (003-005 are taken). The no-results page already shows a "Bu kitaby soraň" placeholder panel
> (`templates/catalogue.html`); task 8 turns it into a request link prefilled with the search.

> **Carried in from Sprint 06 (2026-09-23):** the admin tab bar has five tabs (overview,
> books, add book, stars, site), which is as many as fit. If fulfilling requests needs its own
> admin section, make room first, e.g. merge "add book" into the books page, rather than adding
> a sixth tab ([ADR-0018](../adr/0018-responsive-website-and-phone-layout.md)). Signed-in pages
> also show the star balance chip in the header.

> **Layout (added 2026-09-23, [ADR-0018](../adr/0018-responsive-website-and-phone-layout.md)):**
> every page in this sprint needs both designs — the website from 48rem and the app-style
> phone layout below it — checked with screenshots at both widths. The request list also gets a
> **Soraglar** tab in the phone tab bar (`templates/base.html`) and a link in the website header.

### 1. Schema

`migrations/006-requests.sql`:

- `requests` — id, user_id, title, author, note, status (`open` / `fulfilled` / `rejected` /
  `merged`), fulfilled_book_id, merged_into_id, created_at, resolved_at
- `request_upvotes` — request_id, user_id, created_at, with a unique constraint on the pair

The unique constraint is what enforces one upvote per reader, in the database rather than in
application logic ([ADR-0009](../adr/0009-anonymous-requests-with-upvotes.md)).

**Done when:** the migration applies and a second upvote from the same reader is rejected by the
constraint.

### 2. Posting a request

A form for signed-in readers: title, optional author, optional note. The `user_id` is stored so
abuse can be traced and rate-limited, and **is never rendered anywhere public or returned by any
endpoint**. Anonymity is the feature; leaking it once is enough to lose it.

Before saving, search the catalogue for the title and show near matches — many requests are for
books that are already there under a different spelling.

**Done when:** a request is posted and appears with no attribution, and posting a title that
already exists offers the existing book first.

### 3. The request list

Public, paginated, ordered by upvote count with newest as a tiebreak. Shows title, author, count
and age. Anyone can read it; only signed-in readers can upvote.

**Done when:** the list is readable by anonymous visitors, ordered correctly, and paginates.

### 4. Upvoting

One per reader per request, reversible. A signed-in reader can see which ones they have already
upvoted.

**Done when:** upvoting twice is impossible, removing an upvote works, and the count is always
the number of rows.

### 5. Fulfilment

In the admin panel: link a request to a book, which closes it and shows everyone who wanted it
that it now exists. Also reject with a reason, for requests that cannot or should not be
fulfilled.

**Done when:** a fulfilled request displays a link to the book, and a rejected one shows its
reason.

### 6. Merging duplicates

Two readers will request the same book under different spellings, and Turkmen transliteration
makes this more common than usual. An admin can merge one request into another, carrying the
upvotes across without double-counting anyone who voted on both.

Without this the list decays into noise within months, which is why it is in this sprint rather
than on a wish list.

**Done when:** merging moves upvotes across, counts each reader once, and the merged request
redirects to its target.

### 7. Rate limiting and abuse controls

A limit on requests per reader per day, and the ability for an admin to block a reader from
posting. Empty or nonsense submissions should be cheap to clear.

**Done when:** the limit fires with a clear message, and a blocked reader cannot post while
keeping their account and stars.

### 8. Connect it to search

The no-results page from Sprint 05 offers to post a request, prefilled with what was searched
for. That moment — a reader looking for something the library does not have — is the only moment
this feature is obviously useful.

**Done when:** a fruitless search leads to a prefilled request form in one click.

## What changed while building it (2026-09-23)

Recorded here so the plan above still matches what exists:

- **Anonymity by construction.** Every public query in `app/requests.py` selects one explicit
  column list (`_PUBLIC`) that has no user id in it, never `requests.*`. Only the `admin_*`
  functions, called behind the admin guard, read the requester. The tests give a requester a
  distinctive id and number and search every public response for them, `/openapi.json`
  included; making the request page print the id fails three of them.
- **The poster is the first upvote**, so a new request starts at 1 and the count always means
  "readers who want this".
- **Three lists:** open requests (by upvotes, then newest), fulfilled ones (newest first), and
  "Goldanlarym" for a signed-in reader: every request they upvoted or posted, whatever its
  status. Rejected requests leave the public lists, so one click clears nonsense, but their page
  and "Goldanlarym" still show the reason to the people who wanted them.
- **Only open requests take upvotes.** Closing one freezes its count.
- **Near matches** are published books and open requests whose folded text contains every word
  of the title, then any one word of four letters or more. If there are any, the form shows
  them and posts only when the reader confirms it is a different book.
- **Admin:** `/admin/requests` lists by status; each request's page offers likely books to
  fulfil with (drafts too: the public link appears once the book is published), likely
  duplicates to merge into, a one-click "empty or nonsense" rejection, a rejection with any
  reason, reopening after a mistaken fulfilment or rejection (not after a merge), and blocking
  the requester from posting. The overview shows the five most wanted.
- **The admin tab bar made room** as Sprint 06 warned: "Kitap goş" left the phone tab bar (it is
  the first button on the books page and stays in the desktop navigation), and Soraglar took its
  place. `tests/test_layout.py` now fails if any tab bar grows past five.
- **Limits:** `REQUEST_LIMITS`, default 3 an hour and 10 a day per reader, counted from the
  requests table. Blocking is `users.requests_blocked`; a blocked reader keeps their account,
  stars, downloads and upvotes.
- **Deleting a book** that fulfilled a request leaves the request fulfilled, saying the book is
  no longer available (`ON DELETE SET NULL`).

## Done when (sprint acceptance)

- [x] A signed-in reader posts a request and it appears anonymously.
- [x] Any visitor reads the list; signed-in readers upvote once each.
- [x] No endpoint or page exposes who made a request.
- [x] An admin fulfils a request by linking a book, and rejects with a reason.
- [x] Duplicates can be merged without losing or double-counting upvotes.
- [x] Rate limiting works.
- [x] Verified end-to-end on localhost, with the request link reachable from a failed search —
      deployment happens in Sprint 02's catch-up pass on the droplet (see
      [ADR-0017](../adr/0017-local-dev-with-placeholder-fixtures.md)). *By hand under uvicorn:
      post, near-match step, upvote from the list, visitor sent to sign in, merge (a reader who
      upvoted both counted once, the duplicate redirecting), fulfilment with a book link; no
      requester number on any public page. Both designs checked in screenshots.*

## Tests

- Posting stores the user id but no public view or endpoint returns it. **Check the JSON
  responses too, not only the rendered pages** — this is how anonymity usually leaks.
- The unique constraint rejects a second upvote.
- Removing an upvote decrements the count.
- Ordering is by count, then recency.
- Merging carries upvotes and counts a reader who voted on both exactly once.
- A fulfilled request links to its book and leaves the open list.
- Request rate limits fire per reader.
- Anonymous visitors can read but not post or upvote.

## Files this sprint creates / touches

`app/requests.py` · `migrations/006-requests.sql` · `templates/requests.html` ·
`templates/request_new.html` · `templates/admin/requests.html` · `templates/catalogue.html`
(no-results link) · `tests/test_requests.py`

## No-gos

- No spending stars on requests. That is Phase 4 and needs refund rules before it can exist.
- No comments or discussion on requests.
- No notification when a request is fulfilled — it needs working SMS, so Phase 2 at the earliest.
- No public fulfilment estimates or promises.
- No reader-uploaded files in response to a request. Only admins add books.

## References

[ADR-0009](../adr/0009-anonymous-requests-with-upvotes.md) ·
[ADR-0017](../adr/0017-local-dev-with-placeholder-fixtures.md) ·
[`../02-phases.md`](../02-phases.md) (Phase 4)
