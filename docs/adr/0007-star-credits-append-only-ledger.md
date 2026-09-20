# ADR-0007: Star balances derive from an append-only ledger

- **Status**: Accepted
- **Date**: 2026-09-20

## Context

Stars are the download credit, and from Phase 2 they are bought with real money. That makes
them the part of this system where being wrong is most expensive: a reader who pays and does not
receive, or who downloads and is charged twice, has a complaint the project must be able to
answer with evidence.

The tempting implementation is a `stars` integer on the user row, incremented and decremented.
It is also the implementation that makes those complaints unanswerable — an overwritten number
has no history, so "I paid yesterday" can only be met with "the number says otherwise".

## Decision

Star movements are rows in an append-only `star_ledger` table. Every row records the reader, a
signed amount, a reason (`grant`, `topup`, `spend`, `refund`), a reference to whatever caused it
(a book, a payment SMS, a request), and a timestamp. **Rows are never updated and never deleted.**
A correction is a new row in the opposite direction, not an edit.

A balance is the sum of a reader's rows. It may be cached for display, but the ledger is the
truth and the cache is always rebuildable from it.

Spending is transactional: checking the balance and writing the spend row happen in one
database transaction, so two simultaneous downloads cannot both pass a check that only one
should have.

## Consequences

### Positive

- Every complaint has an answer, with timestamps.
- Corrections are visible as corrections. A grant that fixes a mistake leaves both the mistake
  and the fix in the record.
- Payment processing becomes safely repeatable: a top-up row carries the identifier of the SMS
  that caused it, so the same message arriving twice — which it will
  ([ADR-0008](0008-sms-forwarding-payment-detection.md)) — can be detected and ignored rather
  than credited twice.
- The admin can see exactly where every star came from and went, which is what Phase 2's
  reconciliation work needs.

### Negative / accepted costs

- A balance is a `SUM` rather than a column read. Trivial at this scale; if the ledger ever
  grows large enough to matter, the answer is a cached balance column reconciled against the
  ledger, not abandoning the ledger.
- The ledger only grows. Rows are tiny, and the disk pressure is entirely from PDFs.
- More care is needed at every write site: nothing may ever touch a balance except by appending
  a row. One helper function should own this, and nothing else should write to the table.

## Alternatives considered

- **A mutable balance column.** Less code, no audit trail, no idempotency, and no way to answer
  a dispute. Rejected on the grounds that this is the money.
- **A balance column plus a separate log table for display.** The common compromise, and the
  worst of both: two sources of truth that will eventually disagree, with no rule for which one
  wins.
- **A full double-entry accounting model.** Correct in the strictest sense and far more structure
  than a single-currency credit system needs.
