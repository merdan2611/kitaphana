-- Sprint 03: one-time codes and sessions (ADR-0006, ADR-0013).
-- Neither table stores a secret in readable form: code_hash is an HMAC of the code keyed with
-- SECRET_KEY (a plain hash of a six-digit code is reversed by trying all million of them), and
-- token_hash is a SHA-256 of a 256-bit random token.

CREATE TABLE otp_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT NOT NULL,
    code_hash TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    -- Set on successful login, when the code is burned by wrong attempts, and when a newer
    -- code for the same phone replaces it. NULL means still usable (if not expired).
    used_at TEXT,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    request_ip TEXT
);

-- Rows double as the rate-limit log, so both lookups are by owner and time.
CREATE INDEX otp_codes_phone_created ON otp_codes (phone, created_at);
CREATE INDEX otp_codes_ip_created ON otp_codes (request_ip, created_at);

CREATE TABLE sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX sessions_user ON sessions (user_id);
