# ADR-0009: Book requests are anonymous and publicly upvoted

- **Status**: Accepted
- **Date**: 2026-09-20

## Context

The library will always be missing books. The request list is how the developer finds out which
ones, and it is the cheapest possible market research: rather than guessing what to digitise
next, read what people are asking for.

For that signal to be any good, asking has to be easy and safe. Two things discourage people
from asking in public: being identifiable, and asking for something nobody else wants. The first
is a privacy question — what someone reads is sensitive, and more so in some places than others.
The second is a design question about whether a request list looks alive.

## Decision

Any signed-in reader can post a request: a title, optionally an author and a note. The request
is **displayed anonymously** — the requester's identity is stored, so that abuse can be traced
and rate-limited, but it is never shown to anyone except the admin, and never exposed by any
endpoint.

Any signed-in reader can **upvote** a request, once. Upvote counts are public and order the
list. Requests cost nothing in Phase 1; charging stars for priority is Phase 4
([`../02-phases.md`](../02-phases.md)).

The admin fulfils a request by linking it to a newly added book, which closes it and shows
everyone who wanted it that it exists now.

## Consequences

### Positive

- Nobody has to attach their name to what they are looking for, which matters more for some
  books than others and costs nothing to provide.
- Upvotes turn a flat list into a ranked one, so the most wanted book is also the most obvious
  thing to work on next.
- Someone arriving to find their book already requested can upvote instead of posting a
  duplicate, which keeps the list readable.
- Requiring an account for both actions keeps the signal honest without asking for anything the
  reader has not already given.

### Negative / accepted costs

- Anonymity removes the social reward of being the person who asked, and the ability to thank
  them publicly when it is fulfilled.
- Near-duplicate requests for the same book under different spellings will accumulate. Turkmen
  transliteration makes this worse than usual. The admin needs a merge action — folding one
  request into another and carrying the upvotes across — or the list decays.
- Free upvotes are only as trustworthy as account creation is costly, which in Phase 1 is not
  very. Acceptable while the audience is invited testers; worth watching afterwards.
- No notification when a request is fulfilled, so the requester may never learn. It is on the
  backlog and needs working SMS first.

## Alternatives considered

- **Named requests.** Enables thanking people and adds social pressure not to spam, at a privacy
  cost the project should not impose on its readers.
- **Requests visible only to the admin.** Simplest and safest, and throws away the upvote signal
  entirely — and with it any sense that the library is used by anyone.
- **Charging stars to request from the start.** Better spam resistance and a stronger signal,
  and it puts a price on the one action that tells the project what to build. Deferred to Phase
  4 as an optional priority mechanism rather than a toll on asking at all.
