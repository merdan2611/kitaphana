# ADR-0010: Bulk import is semi-automatic, with a manual queue

- **Status**: Accepted
- **Date**: 2026-09-20

## Context

Phase 3 imports an existing collection of roughly 30 GB of PDFs. Catalogue metadata — title,
author, year, language — has to come from somewhere. The files themselves are unreliable:
filenames are inconsistent, embedded PDF metadata is often empty or wrong, and many are scans
with no text layer at all.

Open Library has an API and covers a great deal of published work. It does not meaningfully
cover books published in Turkmen, which are most of this collection. So automatic matching will
work for part of the import and fail for the majority, and a design that assumes otherwise will
produce a catalogue full of confidently wrong metadata.

## Decision

Import runs as a script in stages:

1. **Hash and de-duplicate.** SHA-256 every file; skip anything already in the library
   ([ADR-0002](0002-local-disk-pdf-storage.md)).
2. **Extract what the file knows** — embedded metadata, page count, a rendered first page to use
   as a cover and as a visual aid for identification.
3. **Try Open Library**, using the filename and any embedded title. A match is accepted only
   above a confidence threshold, and what was matched is recorded so a bad threshold can be
   audited later.
4. **Everything else goes to a manual entry queue** — an admin page showing the rendered first
   page beside a metadata form, so identifying a book is looking at its cover and typing, at a
   target of well under a minute each.

The script is **re-runnable**. Running it twice creates nothing twice.

## Consequences

### Positive

- The easy books are free, and the hard ones are fast rather than automatic — which is the
  honest shape of this problem.
- First-page rendering turns cataloguing from a filename-guessing exercise into recognition,
  which is much quicker and much more accurate.
- Re-runnability means the import can be done in batches over many evenings, which is what
  five-to-ten-hour weeks actually allow.
- Recording the provenance of each match makes a systematic mistake findable afterwards.

### Negative / accepted costs

- The manual queue is genuinely hours of work — at a minute per book, a thousand books is
  most of a phase. This is the real cost of Phase 3 and should be planned for rather than
  discovered.
- Open Library results skew towards English editions, so a loose threshold will attach the wrong
  book's metadata to a Turkmen scan. Better to reject and queue than to accept and be wrong.
- Rendering first pages needs a PDF library and some CPU. On 2 vCPU it should run at low
  priority, or on the developer's machine before upload.
- Getting 30 GB onto the server is itself a task with a real duration — R5 in
  [`../04-risks-and-research.md`](../04-risks-and-research.md).

## Alternatives considered

- **Fully automatic import.** Fast and produces a catalogue that cannot be trusted, which is
  worse than a smaller catalogue that can.
- **Fully manual entry.** Accurate and roughly a thousand hours.
- **OCR every scan to extract a title page.** Would help where Open Library cannot, and costs
  far more CPU than this server has. On the backlog; not a Phase 3 dependency.
- **Crowdsourcing metadata to readers.** Free labour, and a moderation burden the project has
  explicitly ruled out taking on ([`../00-vision.md`](../00-vision.md)).
