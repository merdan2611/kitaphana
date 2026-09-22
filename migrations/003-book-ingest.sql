-- Sprint 04: what ingest needs on top of the Sprint 01 books table (ADR-0002, ADR-0017).

-- The name the file had when uploaded. The file on disk is named by content hash, so this is
-- the only record of what a human called it.
ALTER TABLE books ADD COLUMN original_filename TEXT;

ALTER TABLE books ADD COLUMN updated_at TEXT;

-- Placeholder books loaded by scripts/seed_fixtures.py. The seed script refuses to run when any
-- book with is_fixture = 0 exists, so fixtures never land in a real catalogue.
ALTER TABLE books ADD COLUMN is_fixture INTEGER NOT NULL DEFAULT 0 CHECK (is_fixture IN (0, 1));

-- The one definition of "visible to the public". Public pages (Sprint 05 onwards) read from
-- this view, never from books directly, so an unpublished book cannot leak through a query
-- that forgot the filter.
CREATE VIEW published_books AS
    SELECT * FROM books WHERE is_published = 1;

CREATE INDEX books_created ON books (created_at);
