-- Sprint 01: the two spine tables. Later sprints add their own tables in their own
-- migrations rather than editing this one (ADR-0016).

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    is_admin INTEGER NOT NULL DEFAULT 0 CHECK (is_admin IN (0, 1)),
    is_blocked INTEGER NOT NULL DEFAULT 0 CHECK (is_blocked IN (0, 1))
);

CREATE TABLE books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    year INTEGER,
    language TEXT NOT NULL,
    description TEXT,
    content_hash TEXT NOT NULL UNIQUE,
    file_size INTEGER NOT NULL,
    page_count INTEGER,
    cover_path TEXT,
    price_stars INTEGER NOT NULL DEFAULT 0,
    is_published INTEGER NOT NULL DEFAULT 0 CHECK (is_published IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
