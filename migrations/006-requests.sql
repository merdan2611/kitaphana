-- Sprint 07: book requests and their upvotes (ADR-0009).
--
-- ANONYMITY: requests.user_id is stored so abuse can be traced and rate-limited. It is never
-- rendered on a public page or returned by any endpoint; only the admin panel shows who asked.
-- The same holds for request_upvotes.user_id: a reader sees their own upvotes, nobody else's.

CREATE TABLE requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    -- Who asked. Never shown publicly (see above).
    user_id INTEGER NOT NULL REFERENCES users (id),
    title TEXT NOT NULL,
    author TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    -- open      - on the public list, can be upvoted
    -- fulfilled - the book is in the library now: fulfilled_book_id says which
    -- rejected  - will not be added; reject_reason says why, and is shown publicly
    -- merged    - a duplicate: merged_into_id is the request its upvotes moved to, and its page
    --             redirects there
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'fulfilled', 'rejected', 'merged')),
    -- SET NULL, so deleting a book (storage.delete_book) is never blocked by a request; the
    -- request stays fulfilled and says the book is no longer available.
    fulfilled_book_id INTEGER REFERENCES books (id) ON DELETE SET NULL,
    merged_into_id INTEGER REFERENCES requests (id),
    reject_reason TEXT,
    -- Folded title and author (app/search.py), so similar requests are found whatever the
    -- spelling of Turkmen letters or capitals.
    search_text TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    -- When it stopped being open; NULL while open.
    resolved_at TEXT,
    CHECK ((status = 'merged') = (merged_into_id IS NOT NULL)),
    CHECK ((status = 'rejected') = (reject_reason IS NOT NULL)),
    CHECK ((status = 'open') = (resolved_at IS NULL)),
    CHECK (status = 'fulfilled' OR fulfilled_book_id IS NULL),
    CHECK (merged_into_id IS NULL OR merged_into_id <> id)
);

CREATE INDEX requests_status ON requests (status, created_at);
-- The per-reader rate limit counts a reader's recent requests.
CREATE INDEX requests_user ON requests (user_id, created_at);

-- One row per reader per request. The primary key is what makes a second upvote from the same
-- reader impossible, in the database rather than in application code. A request's count is
-- always the number of its rows; it is never stored.
CREATE TABLE request_upvotes (
    request_id INTEGER NOT NULL REFERENCES requests (id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (request_id, user_id)
);

-- "The requests I upvoted" reads by reader.
CREATE INDEX request_upvotes_user ON request_upvotes (user_id);

-- An admin can stop a reader posting requests without touching their account or their stars.
ALTER TABLE users ADD COLUMN requests_blocked INTEGER NOT NULL DEFAULT 0
    CHECK (requests_blocked IN (0, 1));
