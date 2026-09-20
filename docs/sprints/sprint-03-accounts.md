# Sprint 03 — Accounts

| | |
|---|---|
| **Status** | ⚪ Pending |
| **Phase** | 1 (usable library, codes on screen) |
| **Milestone** | M3 — I can log in |
| **Estimated time** | ~1 week (5-10 hours) |
| **Depends on** | Sprint 02 |

## Goal

Sign-up and sign-in with a phone number and a one-time code, where the code appears on screen
instead of arriving by SMS ([ADR-0013](../adr/0013-dev-otp-mode.md)). Everything around the
delivery — generation, hashing, expiry, single use, rate limiting — is exactly what will run in
production, so Phase 2 replaces one function and nothing else.

Rate limiting belongs in this sprint specifically because codes are free right now. In Phase 2
each one costs money, and a missing rate limit stops being an abuse problem and becomes a bill.

## You can now…

…sign up with your phone number, get a code on screen, log in, close the browser, come back
tomorrow and still be logged in.

## Tasks

### 1. Phone number normalisation

One function turning everything a Turkmen reader might type — `+993 6X XXXXXX`, `8 6X XXXXXX`,
`6XXXXXXX`, with spaces, dashes or brackets — into the single canonical form `+993XXXXXXXX`, and
rejecting anything that is not a plausible Turkmen mobile number. Every path into the system
uses it: sign-up, login, and in Phase 2 the payment webhook.

This is the highest-value unit test in the project. If the same person can reach two different
accounts, or a payment cannot find the account that made it, it will be because of this
function.

**Done when:** every accepted input format maps to one identical stored string, and implausible
numbers are rejected with a message a reader can act on.

### 2. Schema for authentication

`migrations/002-auth.sql` adding:

- `otp_codes` — phone, code_hash, expires_at, used_at, attempt_count, created_at, request_ip
- `sessions` — token_hash, user_id, created_at, expires_at, last_seen_at

Neither table stores a secret in plain text: codes and session tokens are stored hashed, so a
leaked database does not hand over live credentials.

**Done when:** the migration applies cleanly and neither table contains a readable code or token
after a login.

### 3. Requesting a code

Generate a six-digit code, store its hash with a short expiry, and — in dev-OTP mode — return it
for display. An existing unused code for that number is invalidated when a new one is requested.

**Crucially:** requesting a code for an unknown number and for a known number must be
indistinguishable to the caller. Otherwise the form is a way to find out who has an account.

**Done when:** a code is generated and shown, expires on schedule, and the response for a
registered and an unregistered number is identical in body, status and timing.

### 4. Verifying a code

Check the hash, the expiry, and that it has not been used. Mark it used on success. Count
attempts and reject the code entirely after a small number of wrong tries, so a six-digit code
cannot be guessed. If the phone number has no account, create one — sign-up and sign-in are the
same action ([ADR-0006](../adr/0006-phone-number-and-otp-auth.md)).

**Done when:** a correct code logs in and cannot be reused; an expired one fails; five wrong
attempts burn the code and require a new one.

### 5. Rate limiting

Limits on code requests per phone number and per source address, over a short and a long window,
with a clear message when one is hit. Limits are configuration, not constants buried in code, so
they can be tightened in Phase 2 without a deployment.

**Done when:** repeated requests from one number and from one address are refused after the
configured threshold, and the refusal is readable rather than a bare 429.

### 6. Sessions

On success, issue a long-lived signed cookie: `HttpOnly`, `Secure`, `SameSite=Lax`, with a long
expiry — asking a reader to re-authenticate often is annoying now and expensive in Phase 2. A
dependency resolves the current reader for every request; logging out deletes the session row
rather than only clearing the cookie.

**Done when:** a session survives a browser restart, logout invalidates it server-side, and a
tampered cookie is rejected.

### 7. Pages and the dev-mode banner

A login page (number, then code), a small "my account" page showing the number and — for now — a
placeholder where the star balance will go, and the header showing signed-in state.

While dev-OTP mode is on, **every page carries an unmissable banner** saying codes are not real
and the site is invite-only.

**Done when:** the whole flow works on a phone-sized screen, and the banner is impossible to
miss and disappears entirely when the mode is off.

### 8. Admin flag and route guard

Mark one user as admin directly in the database, and add the guard that Sprint 04's admin pages
will sit behind. An admin is a user with a flag, not a separate login system.

**Done when:** a non-admin requesting an admin URL gets a 404 — not a 403, which would confirm
the page exists.

## Done when (sprint acceptance)

- [ ] A new number becomes an account through the on-screen code with no other step.
- [ ] Sessions persist across browser restarts and end properly on logout.
- [ ] Codes expire, cannot be reused, and cannot be brute-forced.
- [ ] Rate limits fire and say so clearly.
- [ ] No code or session token is readable in the database.
- [ ] The dev-mode banner is visible on every page, and vanishes when the flag is off.
- [ ] Deployed and working on `https://<domain>`.

## Tests

- **Phone normalisation, thoroughly** — every input format, plus rejections. The one place to be
  exhaustive.
- A code verifies once and fails the second time.
- An expired code fails.
- Wrong attempts burn the code at the configured threshold.
- Rate limits trigger per number and per address.
- A tampered or unknown session cookie is treated as signed out.
- An admin route returns 404 for a normal user.
- With dev-OTP off, the code is absent from the response body.

## Files this sprint creates / touches

`app/auth.py` · `app/phone.py` · `app/sessions.py` · `app/ratelimit.py` ·
`migrations/002-auth.sql` · `templates/login.html` · `templates/account.html` ·
`templates/base.html` (banner, signed-in header) · `tests/test_phone.py` · `tests/test_auth.py`

## No-gos

- No real SMS. That is Phase 2, and this sprint exists to make it a one-function change.
- No passwords, no email, no account recovery flow.
- No profile: no name, no avatar, no preferences.
- No admin pages yet — only the flag and the guard.
- No stars. The balance placeholder stays a placeholder until Sprint 06.

## References

[ADR-0006](../adr/0006-phone-number-and-otp-auth.md) ·
[ADR-0013](../adr/0013-dev-otp-mode.md) ·
[R2, R3 in risks](../04-risks-and-research.md)
