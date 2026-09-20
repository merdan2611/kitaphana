# ADR-0006: Accounts are a phone number and an SMS code

- **Status**: Accepted
- **Date**: 2026-09-20

## Context

Kitaphana needs accounts, because downloads are metered against a star balance and a balance
has to belong to someone. It needs as little else as possible: every field on a sign-up form is
a reason for somebody to leave.

Two local facts decide this. Email is not how most of the intended readers identify themselves
online — a phone number is. And payment arrives as a mobile operator transfer
([ADR-0008](0008-sms-forwarding-payment-detection.md)), which identifies the payer by their
phone number and nothing else. If accounts were keyed on anything but a phone number, every
payment would need a manual step to work out whose it was.

## Decision

An account is a phone number. Signing up and signing in are the same action: enter the number,
receive a one-time code, enter the code. There is no password, no email address, no username.
Numbers are normalised to `+993XXXXXXXX` on the way in, so the same person typing `8 6X XX XX XX`
or `+993 6X XX XX XX` reaches the same account.

Codes are short-lived, single-use, stored hashed rather than in plain text, and rate-limited per
number and per source address. Sessions are long-lived: asking for a code often would be both
annoying and, once SMS is real, expensive.

## Consequences

### Positive

- The shortest possible sign-up: one field, then one code.
- Nothing to forget and no password reset flow to build, which is a whole feature avoided.
- The account identifier is exactly the identifier payments arrive with, so reconciliation is a
  lookup rather than a judgement call.
- No password database to leak.

### Negative / accepted costs

- **The phone number is the account.** Losing the number means losing the account, including any
  stars bought. Turkmen operators reassign numbers, so a recycled number could reach someone
  else's library account — the admin needs the ability to detach a number from an account.
- Once codes go out by real SMS, every login attempt costs money, which makes rate limiting a
  financial control and not just an anti-abuse one. It is built in Sprint 03, while codes are
  still free, precisely so that it exists before it is needed.
- Users abroad with non-Turkmen numbers are second-class: normalisation is built for `+993`, and
  delivery to foreign numbers may not work at all. Accepted — the primary audience is domestic.
- One phone, one account. Sharing a device means sharing a library account.

## Alternatives considered

- **Email and password.** Free to send and familiar to build, and the wrong identifier for this
  audience, with the additional cost of password storage, reset flows, and no connection to how
  payments arrive.
- **Phone number with a password**, using SMS only for recovery. Fewer messages sent, and a
  password to forget and a reset path to build — which would go over SMS anyway.
- **OAuth with Google or Telegram.** Removes the SMS cost and adds a dependency on a foreign
  service being reachable, while still leaving payments unmatched to accounts.
