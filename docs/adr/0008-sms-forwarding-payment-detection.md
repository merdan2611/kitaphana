# ADR-0008: Detect payments with a forwarding phone and a webhook

- **Status**: Accepted
- **Date**: 2026-09-20

## Context

Readers buy stars by sending mobile credit to a project phone number. There is no payment API
to call: the only notification that money has arrived is an SMS from the operator to that
number. Card payment gateways available to a small project in Turkmenistan are, in practice, not
available at all.

So the problem is getting the contents of an SMS, received on a physical phone, into the
application.

## Decision

A dedicated Android phone holds the project's number and runs an SMS-forwarding application that
posts every received message to a webhook on the backend. The backend parses the message for
the sender's number and the amount, finds the account registered to that number, and appends a
`topup` row to the star ledger ([ADR-0007](0007-star-credits-append-only-ledger.md)).

The endpoint is built defensively, because it is a public URL that creates money:

- Authenticated with a shared secret, over HTTPS only.
- **Idempotent** on the message's identifier. The same SMS will be delivered twice; it must
  credit once.
- **Never silently discards.** Every message is stored raw before it is parsed. Anything that
  fails to parse, or that matches no account, goes to an admin queue — an unrecognised payment
  is someone's money, and it is better sitting in a queue than dropped.
- Monitored by a heartbeat, so silence from the phone raises an alert instead of looking like a
  quiet week.

## Consequences

### Positive

- Works with the payment method readers actually have, with no gateway, no contract and no
  foreign banking relationship.
- Top-ups are automatic in the normal case, which is what makes selling stars viable for a
  developer with five hours a week.
- Raw message storage means a parser improved later can be re-run against everything that ever
  arrived.

### Negative / accepted costs

- **A physical phone is now infrastructure.** It needs power, signal, a charged battery, an app
  that has not been killed by Android's battery optimiser, and a working data connection. It is
  the least reliable component in the system and the one whose failure hurts most, which is why
  the heartbeat is part of the decision rather than a later refinement.
- The parser depends on the operator's exact message wording. If the operator changes it,
  payments stop matching — and the raw-storage plus admin-queue design is what turns that from
  silent data loss into visible work.
- **The whole design assumes the payment SMS contains the payer's phone number.** This has not
  been verified. It is R3 in [`../04-risks-and-research.md`](../04-risks-and-research.md), it
  blocks Phase 2, and the answer is one small self-transfer away. If the number is absent,
  the fallback is a reference code the payer includes in the transfer, which is worse for users
  and would need its own ADR.
- A public endpoint that creates credit is the most attractive target in the system. The shared
  secret is the only thing in front of it.

## Alternatives considered

- **A card payment gateway.** Not realistically available; would also exclude readers without
  cards, who are most of them.
- **Fully manual top-ups** — read the SMS, type the stars in. Correct for Phase 1, where grants
  are done by hand anyway, and does not survive contact with more than a few purchases a day.
- **An operator merchant API.** Would be far better if it exists and is obtainable by an
  individual. Worth asking about, but not something to plan around.
- **A GSM modem on the server instead of a phone.** Fewer moving parts in software, more in
  hardware, and harder to replace locally when it fails.
