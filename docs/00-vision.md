# Vision

## What Kitaphana is

Kitaphana is a web library of books in Turkmen. Readers search a catalogue, open a book's
page, and download the PDF. Downloads are metered with **stars**, a prepaid credit bought by
mobile operator transfer. If a book is not in the library, anyone can request it, and other
readers can upvote that request so the most wanted books get added first.

*Kitaphana* means "library" in Turkmen.

## Why it exists

Books in Turkmen are scarce online. What exists is scattered across chat groups, file-sharing
links that expire, and personal hard drives — findable only if you already know someone who
has the file. There is no single place to look, no search, and no way to say "I am looking for
this book" and have anyone hear it.

This project starts from a concrete asset: a personal collection of roughly 30 GB of PDFs that
is useful to far more people than currently have access to it. The library is the mechanism for
opening that collection up, and the request system is the mechanism for learning what else
should be in it.

## Who it is for

- **Readers in Turkmenistan** on mobile connections that are slow and sometimes metered. This
  is the primary audience and the one every performance decision is made for.
- **Students** looking for specific textbooks and reference works, who usually arrive knowing
  exactly which title they want.
- **Turkmen speakers abroad** who have no physical access to a Turkmen bookshop at all.

## Why stars exist

Running the library costs money every month and disk space is finite. Stars do three things:
they let the running cost be shared by the people using it, they make bulk scraping of the
whole collection expensive rather than free, and they give the request system a currency to
work with later (Phase 4). Some books are free to download; others cost stars. That balance
is an editorial decision, adjustable per book from the admin panel.

## Design principles

1. **Assume a slow phone.** Pages are server-rendered HTML with little CSS and almost no
   JavaScript. A book page should be useful before any image has loaded.
2. **Boring technology.** One developer with 5-10 hours a week cannot afford to debug a
   framework as well as the product. Everything here should be re-understandable after a
   two-week gap.
3. **The catalogue is the product.** Features are worth less than books. When a sprint could
   add either, it adds books.
4. **The least account possible.** A phone number and a code. No email, no username, no
   password to forget.
5. **Every download is accounted for.** Stars are money someone paid, so balances are derived
   from an append-only ledger, not from a number that gets overwritten.

## Anti-goals

Things Kitaphana will deliberately **not** be:

- **Not a social network.** No profiles, no following, no comments under books. Requests have
  upvotes and nothing else, and they are anonymous.
- **Not a reading platform** (at least not before the backlog phase). It hands you a PDF; your
  device reads it.
- **Not a mobile app.** A website that works well on a phone browser, installable as nothing.
- **Not DRM.** The file you download is an ordinary PDF with no protection on it. Any other
  choice would be both hostile and ineffective.
- **Not an upload-anything site.** Only admins add books. There is no public upload queue to
  moderate, because moderation is work that a solo project cannot absorb.
- **Not multi-region.** One server, one country, one language.

## What success looks like

Modest, checkable signals rather than growth targets:

| When | Signal |
|---|---|
| End of Phase 1 | 5-10 invited testers each complete sign-up → search → download without being talked through it |
| End of Phase 2 | A real star purchase by someone who is not the developer credits correctly, unaided |
| End of Phase 3 | The catalogue passes ~1,000 books and search is still the way people find them |
| Ongoing | Requests get fulfilled faster than they accumulate |

The failure signal to watch for is different from all of these: people finding a book, wanting
it, and not completing the download. That is the funnel that matters.

## Shape of the work

Four phases, described in [`02-phases.md`](02-phases.md): a testable MVP with on-screen OTP
codes, then real SMS and real payments, then the bulk import of the existing collection, then
star-prioritised requests.
