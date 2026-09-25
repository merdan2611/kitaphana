# Sprint 07 — Requests

| | |
|---|---|
| **Status** | ⚪ Pending |
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

## Done when (sprint acceptance)

- [ ] A signed-in reader posts a request and it appears anonymously.
- [ ] Any visitor reads the list; signed-in readers upvote once each.
- [ ] No endpoint or page exposes who made a request.
- [ ] An admin fulfils a request by linking a book, and rejects with a reason.
- [ ] Duplicates can be merged without losing or double-counting upvotes.
- [ ] Rate limiting works.
- [ ] Verified end-to-end on localhost, with the request link reachable from a failed search —
      deployment happens in Sprint 02's catch-up pass on the droplet (see
      [ADR-0017](../adr/0017-local-dev-with-placeholder-fixtures.md)).

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
