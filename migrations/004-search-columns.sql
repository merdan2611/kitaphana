-- Sprint 05: a folded copy of each book's title and author, for search (app/search.py).
--
-- SQLite's LIKE folds case for ASCII only, so without this, searching "älem" misses "Älem",
-- and "alem" typed on a phone without Turkmen letters finds nothing. The app writes this column
-- whenever it saves a book (storage.ingest, the admin edit form). The UPDATE below fills it for
-- books that already exist, through the same Python function: app/db.py registers it with every
-- connection as kitaphana_fold, which is why migrations must run through scripts/migrate.py.

ALTER TABLE books ADD COLUMN search_text TEXT NOT NULL DEFAULT '';

UPDATE books SET search_text = kitaphana_fold(title || ' ' || author);

CREATE INDEX books_language ON books (language);
