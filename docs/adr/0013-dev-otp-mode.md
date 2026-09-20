# ADR-0013: Ship Phase 1 with OTP codes shown on screen

- **Status**: Accepted
- **Date**: 2026-09-20

## Context

Accounts depend on delivering a code by SMS ([ADR-0006](0006-phone-number-and-otp-auth.md)), and
SMS delivery depends on the forwarder phone, an operator relationship, and answers to questions
that are not yet answered ([ADR-0008](0008-sms-forwarding-payment-detection.md), R2 and R3 in
[`../04-risks-and-research.md`](../04-risks-and-research.md)).

If authentication had to wait for real SMS, nothing downstream of it could be tested — which is
nearly everything: the catalogue, stars, downloads, requests, the admin panel. Phase 1 would end
with a pile of untested code and its first real test would be the same day as its first real
users.

## Decision

Phase 1 runs in **dev-OTP mode**: the login page displays the one-time code in the browser
instead of sending it anywhere. Everything else about authentication is real — the code is
generated, stored hashed, expires, is single-use, and is rate-limited exactly as it will be in
production. Only the delivery channel is replaced.

The mode is controlled by an environment variable, and:

- The default is **off**. A missing or unparseable variable means no code is shown.
- When it is on, every page carries an unmissable banner saying so, so it cannot be running
  quietly.
- Switching it off is a Phase 2 exit criterion, verified by an actual login attempt, not by
  reading configuration.

## Consequences

### Positive

- The entire product can be built, deployed and tested end to end before any SMS plumbing
  exists. Phase 1's exit criteria are all reachable.
- Testers can be invited — with a clear explanation — while codes are still on screen, so real
  feedback arrives months earlier than it otherwise would.
- Because the surrounding machinery is real, turning on real SMS in Phase 2 changes one function
  and nothing else. Rate limits, expiry and hashing are already proven by then.
- Any login works during development without waiting for or paying for a message.

### Negative / accepted costs

- **Anyone who knows a phone number can log into that account.** This is a complete bypass of
  authentication, which is precisely what it is for. It means Phase 1 is invite-only, the
  testers must be told, and nothing genuinely sensitive can be in an account until Phase 2.
- Leaving it enabled in production after Phase 2 would be the single worst mistake available in
  this codebase. The default-off setting and the banner exist because of that, and the exit
  criterion is verified by behaviour rather than configuration.
- Stars bought during Phase 1 do not exist — balances come from admin grants
  ([ADR-0007](0007-star-credits-append-only-ledger.md)) — so the purchase path is genuinely
  untested until Phase 2.
- Real SMS delivery brings failures that dev mode cannot simulate: delays, non-delivery,
  operator filtering. Those surface for the first time in Phase 2.

## Alternatives considered

- **Wait for real SMS before building accounts.** Blocks every other feature on an external
  dependency with open questions. Rejected as the fastest route to a dead project.
- **Print the code to the server log** rather than the screen. Slightly safer and much worse to
  test with, especially for testers who have no log access. The banner covers the same risk more
  visibly.
- **A fixed code such as `000000` in development.** Simpler and exercises less of the real path —
  no generation, no expiry, no single-use behaviour — so the parts most likely to be wrong stay
  untested.
- **A paid SMS gateway for testing.** Costs money on every login during the phase with the most
  logins, to test something that will be replaced by the operator path anyway.
