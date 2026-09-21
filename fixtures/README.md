# Fixtures

Placeholder catalogue content for local development, used until the VDS exists and the real
~30 GB collection is imported in Phase 3. See
[ADR-0017](../docs/adr/0017-local-dev-with-placeholder-fixtures.md) for why this exists and
[`sprint-04-admin-and-ingest.md`](../docs/sprints/sprint-04-admin-and-ingest.md) for the seed
script that loads it.

## What's here

```
fixtures/books/
  manifest.yaml
  <slug>.pdf   one file per entry in the manifest
```

## `manifest.yaml`

One entry per placeholder book:

```yaml
- filename: some-slug.pdf
  title: "…"
  author: "…"
  year: 1900
  language: "en"          # or "tk", matching the books.language column
  price_stars: 0
  source: "Where this text came from, and why it is public domain — e.g. a Project Gutenberg
    or Wikisource URL and the year of the author's death, or a note that it predates any
    copyright term. Keep this honest; it is the provenance record R9 in
    ../docs/04-risks-and-research.md asks the project to keep."
```

## Rules

- **Every file here must be genuinely public domain.** The `source` field is not optional — it
  is what makes that claim checkable later, by anyone, including a future version of the
  developer who has forgotten the details.
- **This directory is for local development only.** The seed script built in Sprint 04 refuses
  to run against a database that already contains real, non-fixture books, so these can never
  reach a live catalogue by an accidental re-run.
- **Not a substitute for the real collection.** These exist so Sprints 01 and 03-07 have
  something real to upload, search and download while there is no VDS to put the actual
  collection on. They say nothing about what belongs in the finished library.
- Keep files small. A handful of short texts is enough to exercise every code path; there is no
  reason for a fixture to be large.

## Status

Empty except for this file. Specific public-domain texts have not been chosen yet — that needs a
small amount of real research into sources whose public-domain status is actually verifiable,
which is worth doing carefully rather than guessing. Do this before Sprint 04's seeding task
needs something to seed.
