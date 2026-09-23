-- Sprint 06: the star ledger (ADR-0007).
--
-- A reader's balance is the sum of their rows here. There is no balance column anywhere: the
-- ledger is the only record, so it is the answer to every "where did my stars go?".
--
-- APPEND-ONLY. Rows are never updated and never deleted; a mistake is corrected by a new row in
-- the opposite direction. The two triggers at the bottom make SQLite refuse an UPDATE or DELETE,
-- and app/stars.py is the only code that writes here (through stars.append_entry).
--
-- Columns:
--   user_id     The reader whose stars moved. No ON DELETE: a user with ledger rows cannot be
--               deleted, because deleting them would delete their history.
--   amount      Signed number of stars. Positive adds to the balance, negative takes from it.
--               Zero only for a spend on a free book, so that the download is still recorded.
--   reason      grant  - added or taken away by hand by an admin; never zero. A negative grant
--                        is a correction.
--               topup  - bought with a payment (Phase 2); always positive.
--               spend  - taken by a download; zero or negative.
--               refund - given back for a spend; always positive.
--   reference   What caused the row, as "<kind>:<id>": "book:12" for a download or a refund of
--               one, a payment id in Phase 2, a request id in Phase 4. NULL for grants.
--   note        Free text. For a grant, the admin's reason, which the reader also sees. For a
--               spend, the book's title at the time, so the history still reads correctly after
--               the book is renamed or deleted.
--   created_at  UTC, in the same text format as every other timestamp (app/db.py).

CREATE TABLE star_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users (id),
    amount INTEGER NOT NULL,
    reason TEXT NOT NULL CHECK (reason IN ('grant', 'topup', 'spend', 'refund')),
    reference TEXT,
    note TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (
        (reason = 'grant' AND amount <> 0)
        OR (reason IN ('topup', 'refund') AND amount > 0)
        OR (reason = 'spend' AND amount <= 0)
    )
);

-- Balances, histories and the download rate limit all read one reader's rows.
CREATE INDEX star_ledger_user ON star_ledger (user_id, created_at);

CREATE TRIGGER star_ledger_no_update BEFORE UPDATE ON star_ledger
BEGIN
    SELECT RAISE(ABORT, 'star_ledger is append-only: add a correcting row instead');
END;

CREATE TRIGGER star_ledger_no_delete BEFORE DELETE ON star_ledger
BEGIN
    SELECT RAISE(ABORT, 'star_ledger is append-only: add a correcting row instead');
END;
