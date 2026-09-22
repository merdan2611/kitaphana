# Sprint 05 — Public catalogue

| | |
|---|---|
| **Status** | 🟢 Shipped — 2026-09-23 |
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

- [x] Books uploaded in Sprint 04 are browsable and searchable by anyone, signed in or not.
- [x] Search handles Turkmen letters in either case.
- [x] Every page works at 360 px wide.
- [x] Unpublished books are invisible everywhere, including by direct URL.
- [x] Empty states are real pages.
- [x] Verified end-to-end on localhost, checked at 360 px width — and opened on an actual phone
      once deployed in Sprint 02's catch-up pass (see
      [ADR-0017](../adr/0017-local-dev-with-placeholder-fixtures.md)). *The localhost part is
      done; the real-phone check waits for that catch-up pass, as planned.*

## Tests

- Only published books appear in catalogue and search results.
- An unpublished book's URL returns 404 for the public.
- Search folding: `alem` / `älem` / `ÄLEM` return the same result.
- Search matches on author as well as title.
- Pagination boundaries: the last page, an out-of-range page, an empty catalogue.
- A book with no cover renders without error.

## Files this sprint creates / touches

`app/catalogue.py` · `app/search.py` · `templates/catalogue.html` · `templates/book.html` ·
`templates/404.html` · `migrations/004-search-columns.sql` · `static/style.css` ·
`tests/test_search.py` · `tests/test_catalogue.py`

*The plan named `003-search-columns.sql`; Sprint 04 had already used 003, so it is 004.*

## No-gos

- No full-text search inside PDF contents. Backlog.
- No recommendations, no "related books", no ratings, no comments — see the anti-goals in
  [`../00-vision.md`](../00-vision.md).
- No reading in the browser.
- No downloads yet. The button exists and explains itself; Sprint 06 makes it work.
- No user-facing collections or shelves.

## Notes from the sprint

- **How search folds text.** `app/search.py` decomposes each letter, case-folds it and drops its
  diacritics, so `alem`, `älem` and `ÄLEM` are the same word. The same goes for every Turkmen
  letter (ä ç ň ö ş ü ý ž) and for Cyrillic case; й and ё fold to и and е on both sides. A search
  matches when every word of the query appears somewhere in the title or author, as a substring.
  Readers can type without a Turkmen keyboard.
- **One folding function, used by both sides.** `books.search_text` is written by the only two
  places that change a title or author: `storage.ingest` and the admin edit form. `app/db.py`
  registers the same Python function with SQLite as `kitaphana_fold`, and migration 004 uses it
  to backfill existing books. A test checks that the Python and SQL results agree. As a
  consequence, **migrations must run through `python -m scripts.migrate`**: the `sqlite3` CLI
  does not know that function and would fail with "no such function".
- **Not solved: Latin typing for Cyrillic titles.** "kashtanka" does not find «Каштанка».
  Transliteration is a real question for this audience, and it is recorded as R10 in
  `04-risks-and-research.md` instead of being guessed at here.
- **Title sort ignores diacritics** (Ä files with A), which is not Turkmen dictionary order
  (… E, Ä, F …). Also part of R10.
- **Measured speed:** with 30,000 synthetic books, a search takes about 20 ms (median) on the
  development laptop. The slowest request is a deep page sorted by title, at about 50 ms. FTS5
  can wait until Phase 3, as planned.
- **Measured page weight:** catalogue HTML is 18 KB (3.4 KB gzipped); `style.css` is 30 KB
  (6.6 KB gzipped). The first 4 covers load immediately and the rest are lazy-loaded; every image
  has width and height set, so nothing jumps. Real text-page covers average about 19 KB, which
  comes to about 100 KB for a phone's first screen and about 370 KB if all 20 covers are
  scrolled into view. If real scans turn out much heavier, a small list thumbnail is the next
  step; that would be new work. Sprint 02's nginx task now includes gzip.
- **Book URLs** are `/books/<id>` with canonical digits only. An unknown, unpublished, malformed
  or out-of-range id all get the same 404 page, including for admins: they use the admin page,
  which now links to the public page once a book is published.
- **One HTML 404 page** serves every 404, including the admin guard's, so it reveals nothing.
  It shows the correct signed-in header even for URLs that match no route.
- **Returning after login:** the book page's button goes to `/login?next=/books/<id>`, and
  after the code the reader is back on the book. Only paths on this site are accepted, which
  tests check against the usual open-redirect tricks. Sprint 06 can use the same mechanism when
  a download needs sign-in.
- **Placeholders for later sprints:** the book page's download button (disabled for signed-in
  readers, "log in" for visitors) is Sprint 06's to make real. The "Bu kitaby soraň" panel on
  the no-results page is Sprint 07's to turn into a prefilled request.
- **The home page** now has a search box where it used to say the catalogue was being prepared.
- **Test-suite fixes found along the way.** One new test had written two test PDFs into the real
  `media/` folder; they were removed, and a session-wide guard now fails the run if any test
  writes there. pytest's own temp folders no longer land in `media/tmp` (a side effect of the
  Sprint 04 upload-spooling setting). `db.connect()` now reads settings at call time, so tests
  never touch `kitaphana.db`.

## References

[ADR-0003](../adr/0003-no-frontend-framework.md) ·
[ADR-0017](../adr/0017-local-dev-with-placeholder-fixtures.md) ·
[`../00-vision.md`](../00-vision.md) ·
[R8 — whether a Russian interface is needed](../04-risks-and-research.md)
