# Sprint 04 — Admin and ingest

| | |
|---|---|
| **Status** | 🟢 Shipped — 2026-09-23 |
| **Phase** | 1 (usable library, codes on screen) |
| **Milestone** | M4 — I can put a book in |
| **Estimated time** | ~1 week (5-10 hours) |
| **Depends on** | Sprint 03 |

## Goal

Get books into the library. An admin uploads a PDF with its metadata; the file is stored by
content hash, duplicates are refused, and the book appears in an admin list where it can be
edited, priced and published.

This is also the first rehearsal for Phase 3. The way a single upload stores and de-duplicates a
file is the same path the bulk importer will use for thirty thousand, so getting it right once
here is worth a great deal later.

## You can now…

…upload a book from your laptop and see it listed in the admin panel with its cover.

## Tasks

### 1. Admin section

An admin layout and index behind the Sprint 03 guard, visually distinct from the public site so
it is never unclear which one you are looking at. Links to books, and later to requests and
readers.

**Done when:** an admin reaches it from the header; a normal reader gets a 404.

### 2. Upload

A form taking a PDF plus title, author, year, language, description and price in stars. The file
is streamed to a temporary location rather than read into memory — an 80 MB upload buffered in
RAM on a 2 GB server is exactly the kind of mistake this project cannot afford. nginx's upload
size limit from Sprint 02 needs to match what you expect to accept.

**Done when:** a large PDF uploads successfully and the server's memory use during the upload is
flat.

### 3. Content hash and de-duplication

Hash the file with SHA-256 while streaming it, then check whether that hash already exists. If it
does, discard the upload and tell the admin which book it duplicates. Otherwise move it into the
media directory under a hash-derived path
([ADR-0002](../adr/0002-local-disk-pdf-storage.md)).

Fan the files out into subdirectories by the first characters of the hash rather than putting
tens of thousands into one directory.

**Done when:** uploading the same file twice under different names is refused the second time,
naming the existing book, and the file lands at a path derived from its hash.

### 4. Extract what the file knows

Page count, file size, and embedded PDF metadata offered as prefilled form values the admin can
correct. Embedded metadata is frequently wrong, so it is a suggestion, never an authority.

**Done when:** page count and size are stored, and embedded title or author appear as editable
suggestions.

### 5. Cover images

Either upload a cover or render the PDF's first page as one. Store a reasonably sized image
rather than a full-resolution render — these load on mobile connections. The catalogue must look
correct for books with no cover at all.

**Done when:** a book gets a cover from a rendered first page, and a book without one still
displays correctly.

### 6. Book list and editing

A paginated admin list with search, showing cover, title, author, price and published state.
Editing metadata, changing the price, and publishing or unpublishing. Unpublished books are
invisible to the public — this is what makes it safe to upload something and finish its metadata
later.

**Done when:** a book can be uploaded unpublished, edited, then published, and only appears
publicly after that last step.

### 7. Deleting a book

Remove the catalogue entry and the file, with a confirmation step. Guard against the case where
two books somehow reference one file.

**Done when:** deleting removes both the row and the file, and asks first.

### 8. Seed the placeholder fixtures

The real collection is not imported until Phase 3, and there is no VDS yet to upload to
([ADR-0017](../adr/0017-local-dev-with-placeholder-fixtures.md)). Write `scripts/seed_fixtures.py`,
reading `fixtures/books/manifest.yaml` and calling the same storage/hashing function this
sprint's upload handler uses for each entry — not a raw database insert, so the seeded books
exercise the exact code path a real upload does.

The script must refuse to run against a database that already contains real, non-fixture books.
Placeholder content must never be able to reach a live catalogue by an accidental re-run.

**Done when:** running the script populates the admin list with the fixture books, each showing
the correct content hash and cover; running it a second time is a no-op; and running it against
a database seeded with at least one non-fixture book refuses with a clear error.

## Done when (sprint acceptance)

- [x] An admin uploads a PDF with metadata and sees it in the list.
- [x] Duplicate uploads are refused and name the existing book.
- [x] Files are stored by hash, fanned out into subdirectories, outside the repository.
- [x] Memory use is flat during a large upload.
- [x] Publishing state controls public visibility.
- [x] No admin page is reachable by a normal reader.
- [x] The placeholder fixtures seed cleanly through the real ingest path and the seed script
      refuses to run against a database with real books already in it.
- [x] Verified end-to-end on localhost — deployment happens in Sprint 02's catch-up pass once
      the VDS is available (see [ADR-0017](../adr/0017-local-dev-with-placeholder-fixtures.md)).

## Tests

- Hashing a known file produces the expected SHA-256.
- A second upload of the same bytes is rejected as a duplicate.
- The hash-to-path mapping is stable and fans out as intended.
- Uploading a file that is not a PDF is rejected.
- Unpublished books are absent from any public query.
- Admin endpoints return 404 for a normal reader — including the upload handler itself, not just
  the page that links to it.

Manually, on localhost: upload the largest PDF you have and watch memory with `htop`. Repeat
against the live server once Sprint 02 has happened.

## Files this sprint creates / touches

`app/admin.py` · `app/storage.py` · `app/pdfmeta.py` · `templates/admin/*.html` ·
`static/admin.css` · `scripts/seed_fixtures.py` · `tests/test_storage.py`

## No-gos

- No bulk import, no Open Library, no import scripts — that is all Phase 3. This sprint handles
  one file at a time on purpose.
- No public catalogue yet; Sprint 05 builds it.
- No stars, no downloads.
- No OCR, no text extraction, no thumbnails beyond the single cover.
- No rich text in descriptions. Plain text.
- Fixtures are never seeded automatically in production, and never by anything other than the
  guarded seed script.

## Notes from the sprint

- **Memory was not flat at first, and the cause was pypdf.** Given a *path*, `PdfReader` reads
  the whole file into a `BytesIO` before parsing. A 150 MB upload raised the server's peak
  memory by 150 MB. `app/pdfmeta.py` now passes an open file, which pypdf reads lazily, and a
  test pins that. Measured afterwards: three 150 MB uploads (valid, garbage, duplicate) left
  uvicorn's peak resident memory at 72 MB against a 71 MB idle baseline.
- **Upload spooling goes to `MEDIA_DIR/tmp`, not `/tmp`.** Starlette spools uploads over 1 MB to
  tempfile's directory, and `/tmp` is often tmpfs, i.e. RAM. `app/main.py` points tempfile at
  the media disk, which also makes the final move a rename rather than a copy.
- **Admin handlers never declare `File`/`Form` parameters.** FastAPI parses those *before*
  dependencies run, so a non-admin could push a 200 MB body at the server before getting the
  404. Handlers that take a body are `async def`, read the form after the guard, and hand the
  blocking work to the thread pool. Publish and unpublish are separate body-less endpoints for
  the same reason.
- **Fixed a Sprint 01 bug along the way:** `connect()` now passes `check_same_thread=False`.
  FastAPI opens the `get_db` connection and runs the handler in separate thread-pool calls,
  which can land on different threads. Under concurrent load that raised `ProgrammingError`.
- **Covers:** `pdftoppm` (poppler) in a subprocess, 360 px wide JPEG, about 15 KB each. It
  runs outside the web process's memory. An uploaded cover goes through Pillow, with a
  25-megapixel cap checked before decoding. Books without a cover get a typeset stand-in:
  title and author on a carpet colour, or just the initial at thumbnail size.
- **`published_books` view** (migration 003) is the one definition of "public". Sprint 05 must
  query it, never `books` directly.
- **Fixtures** are five Wikisource exports in Turkmen, English and Russian; see
  `fixtures/README.md` for provenance.
- **Frontend pass:** a new public design (madder red, göl carpet-border strip, serif headings,
  no webfonts) and a visually separate admin (indigo bar, grey desk). The dev banner is now
  saffron with a hazard edge, a colour nothing else on the site uses.
  *Replaced the same day:* the owner preferred classic colours and asked for separate website
  and phone designs — see [ADR-0018](../adr/0018-responsive-website-and-phone-layout.md).
- **Deliberately not done:** there is no admin preview of the stored PDF, because serving PDFs
  through Python is ruled out (ADR-0014); Sprint 06 builds the download path. Admin search is
  `LIKE`, which is ASCII-only for case-folding, so Cyrillic search is case-sensitive; Sprint 05
  owns real search.

## References

[ADR-0002](../adr/0002-local-disk-pdf-storage.md) ·
[ADR-0010](../adr/0010-semi-automatic-bulk-import.md) ·
[ADR-0014](../adr/0014-x-accel-redirect-for-downloads.md) ·
[ADR-0017](../adr/0017-local-dev-with-placeholder-fixtures.md)
