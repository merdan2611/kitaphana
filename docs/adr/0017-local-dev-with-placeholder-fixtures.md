# ADR-0017: Develop locally with placeholder fixtures before the VDS is available

- **Status**: Accepted
- **Date**: 2026-09-21

## Context

The roadmap as originally written assumed two things would exist by the time they were needed:
a purchased VDS by Sprint 02, and real catalogue content — the existing ~30 GB collection — by
the time Sprints 04-06 needed something to upload, browse and download. Neither is true as of
this decision, and there is no firm date for either. Sprint 01 has not started; no application
code exists yet.

Left as written, this quietly blocks more than it should. `sprint-03-accounts.md` names Sprint
02 as a dependency, even though accounts do not need a live server to build or test. Every
sprint from 03 through 07 has "deployed and working on the live domain" as an acceptance
criterion, which makes finishing a sprint depend on buying a server — a non-technical, external
blocker the developer does not control the timing of. And Sprints 04-06 have no content to work
with at all until Phase 3's bulk import, which is much later in the plan.

## Decision

Sprints 01 and 03 through 07 are built and fully tested on `localhost`, using a small set of
real public-domain PDFs as placeholder catalogue content, committed to the repository under
`fixtures/books/`. Sprint 02 — the real VDS, domain, and TLS — runs whenever the VDS is actually
purchased, independent of which other sprint is in progress. It is no longer a prerequisite for
anything except itself and Phase 1's final exit criterion.

Because sprints may now finish locally well before Sprint 02 happens, Sprint 02 gains a final
task: a **catch-up verification** pass that re-runs the acceptance checklist of every sprint
completed before it, against the real server, once the server exists.

Fixtures are for local development only. The seed script that loads them is built in Sprint 04,
goes through the same storage and hashing code path a real admin upload would use — not a raw
database insert — and refuses to run against a database that already contains real, non-fixture
books, so it can never contaminate a live catalogue. Each fixture's `manifest.yaml` entry
records a `source` field citing exactly where the text came from and why it is public domain,
which doubles as the provenance record that R9 in
[`../04-risks-and-research.md`](../04-risks-and-research.md) already asks the project to keep.

Sprint numbers and filenames are unchanged. This is a resequencing of dependencies, not a
renumbering.

## Consequences

### Positive

- Development is no longer stalled on an external purchase with no timeline. Six of eight Phase
  1 sprints can be built and genuinely tested without a VDS.
- Real public-domain texts, rather than synthetic placeholders, mean the catalogue, search and
  download flow look and behave like the real product during local testing and any early demo.
- Seeding through the real ingest path exercises exactly the code that matters — hashing,
  de-duplication, metadata storage — rather than bypassing it with a shortcut that would leave
  that code untested until real content arrives.
- The provenance field on each fixture is a small, concrete first step on the copyright question
  in R9, applied to content the project controls completely.

### Negative / accepted costs

- Phase 1's original rationale — "deploy early so the unfamiliar risk is faced in week two, not
  week eight" — no longer holds by default. It still applies the moment the VDS exists: Sprint 02
  should be run as soon as possible after that, not deferred further. This ADR removes a hard
  gate, not the underlying advice.
- The catch-up verification task in Sprint 02 is real, non-trivial work that did not exist in
  the original plan — potentially re-checking five sprints' worth of acceptance criteria in one
  pass instead of one sprint's worth at a time.
- A guard that refuses to seed fixtures into a non-empty production-shaped database is now a
  required piece of code, not an optional nicety — without it, a misconfigured script could put
  placeholder books in front of real readers.
- Local testing cannot exercise anything that only exists in production: real TLS, real network
  latency to Turkmenistan, nginx's `X-Accel-Redirect` behaviour
  ([ADR-0014](0014-x-accel-redirect-for-downloads.md)) needs its own local-mode fallback, systemd
  restart behaviour, and so on. These stay genuinely unverified until Sprint 02's catch-up pass.

## Alternatives considered

- **Wait for the VDS before writing any code.** Simplest to reason about, and leaves the project
  stalled for an unknown period on a purchase decision that has nothing to do with development
  readiness. Rejected.
- **Synthetic, generated placeholder content** (lorem-ipsum text, obviously fake titles). Zero
  provenance concerns and no risk of the placeholders being mistaken for real value, at the cost
  of a demo that looks nothing like the eventual product. Rejected — the developer specifically
  wants real public-domain texts so early testing and any preview looks like the real thing.
- **Renumber the sprints** so the locally-buildable ones come first and Sprint 02 moves to the
  end. Would better reflect the new execution order, and it renames files that ADRs, the
  roadmap, and this document already reference, for a benefit ADR-0017's dependency changes
  already deliver without renaming anything.
