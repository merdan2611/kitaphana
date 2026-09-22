# Sprint 05 — Public catalogue

| | |
|---|---|
| **Status** | ⚪ Pending |
| **Phase** | 1 (usable library, codes on screen) |
| **Milestone** | M5 — I can find a book |
| **Estimated time** | ~1 week (5-10 hours) |
| **Depends on** | Sprint 04 |

## Goal

Turn the books uploaded in Sprint 04 into something a reader can browse and search. This is the
first sprint whose output a reader actually sees, and the first chance to find out whether the
site is usable on a phone on a slow connection.

## You can now…

…open the site on your phone, type part of a title, and get to that book's page.

## Tasks

> **Layout (added 2026-09-23, [ADR-0018](../adr/0018-responsive-website-and-phone-layout.md)):**
> every page in this sprint needs both designs — the website from 48rem and the app-style
> phone layout below it — checked with screenshots at both widths. The catalogue also gets a
> **Katalog** tab in the phone tab bar (`templates/base.html`) and a link in the website header.

### 1. Catalogue page

A paginated grid or list of published books: cover, title, author, year, price in stars. Server
rendered, cheap, and correct for books without covers. Pagination is links, not infinite scroll
([ADR-0003](../adr/0003-no-frontend-framework.md)).

**Done when:** the catalogue lists published books only, paginates, and is usable at 360 px
wide.

### 2. Search — and the Turkmen letter problem

Search across title and author. The obvious implementation is `WHERE title LIKE '%…%'`, and it
has a specific trap worth knowing before you hit it: **SQLite's default case-insensitivity only
applies to ASCII.** `LIKE` will match `kitap` against `Kitap`, but it will not match `älem`
against `Älem`, or fold `Ň`, `Ý`, `Ş`, `Ž`, `Ö` or `Ü`. For a Turkmen-language catalogue that
means search quietly fails on a large share of titles, in a way that looks like missing books
rather than broken search.

Fix it by storing a folded search column: lowercase and normalise the title and author in
Python when a book is saved, and match the query — folded the same way — against that column.
One function does the folding and both sides use it.

SQLite's FTS5 is the better long-term answer and should be revisited in Phase 3 when the
catalogue is a thousand books rather than twenty; it has its own tokenisation questions for
Turkmen, which is why this sprint does the simple thing well instead.

**Done when:** searching for `alem`, `älem` and `ÄLEM` all find the same book, and results
appear in well under a second.

### 3. Book page

Cover, full metadata, description, price, and a download button whose behaviour depends on
signed-in state and — from Sprint 06 — balance. For now the button is present and explains that
downloads arrive next sprint.

**Done when:** the page renders for signed-in and anonymous visitors, each seeing an appropriate
call to action.

### 4. Browsing without searching

Filter by language and sort by newest, as links rather than a JavaScript control. Most readers
arrive knowing what they want, but the ones who do not need a way in.

**Done when:** filters and sorting work as ordinary links with shareable URLs.

### 5. Empty and error states

A search with no results, a catalogue with no books, an unknown book, an unpublished book.
Each gets a real page — the no-results page should suggest posting a request, which is the
bridge to Sprint 07.

**Done when:** none of these cases shows a stack trace or a blank page, and no-results offers
the request route.

### 6. Make it fast on a phone

Size cover images appropriately, add width and height attributes so the layout does not jump,
lazy-load images below the fold, and check the page weight. A book page should be useful before
any image has loaded.

**Done when:** a catalogue page is comfortably under a few hundred kilobytes including covers,
and text is readable before images arrive.

## Done when (sprint acceptance)

- [ ] Books uploaded in Sprint 04 are browsable and searchable by anyone, signed in or not.
- [ ] Search handles Turkmen letters in either case.
- [ ] Every page works at 360 px wide.
- [ ] Unpublished books are invisible everywhere, including by direct URL.
- [ ] Empty states are real pages.
- [ ] Verified end-to-end on localhost, checked at 360 px width — and opened on an actual phone
      once deployed in Sprint 02's catch-up pass (see
      [ADR-0017](../adr/0017-local-dev-with-placeholder-fixtures.md)).

## Tests

- Only published books appear in catalogue and search results.
- An unpublished book's URL returns 404 for the public.
- Search folding: `alem` / `älem` / `ÄLEM` return the same result.
- Search matches on author as well as title.
- Pagination boundaries: the last page, an out-of-range page, an empty catalogue.
- A book with no cover renders without error.

## Files this sprint creates / touches

`app/catalogue.py` · `app/search.py` · `templates/catalogue.html` · `templates/book.html` ·
`templates/404.html` · `migrations/003-search-columns.sql` · `static/style.css` ·
`tests/test_search.py`

## No-gos

- No full-text search inside PDF contents. Backlog.
- No recommendations, no "related books", no ratings, no comments — see the anti-goals in
  [`../00-vision.md`](../00-vision.md).
- No reading in the browser.
- No downloads yet. The button exists and explains itself; Sprint 06 makes it work.
- No user-facing collections or shelves.

## References

[ADR-0003](../adr/0003-no-frontend-framework.md) ·
[ADR-0017](../adr/0017-local-dev-with-placeholder-fixtures.md) ·
[`../00-vision.md`](../00-vision.md) ·
[R8 — whether a Russian interface is needed](../04-risks-and-research.md)
