# Phases

Four phases. Each one ends with something that can be used by hand, not just something that
compiles. The rule that shapes every phase boundary: **at the end of it, there is a sentence
starting with "I can now…" that a person could verify in a browser.**

Only Phase 1 has sprint documents written. Later phases have goals and exit criteria here;
their sprint documents get written when the phase is reached, informed by what actually
happened in Phase 1. Estimates are in weeks at 5-10 hours per week and will be wrong.

---

## Phase 1 — A library you can use, with codes on screen

**Goal:** the complete loop — sign up, find a book, spend stars, get the PDF, request a
missing book — live on the real domain, on the real server, over HTTPS. The only thing that
is fake is SMS delivery: OTP codes appear in the browser instead of arriving by text
([ADR-0013](adr/0013-dev-otp-mode.md)). Everything else is production.

This phase is deliberately front-loaded with deployment. Sprint 02 puts a nearly empty
application on the live server, because server administration is the least familiar part of
this project and the worst possible time to learn it is the week before launch. From Sprint 02
onward every sprint ends with a deploy, so deployment is never an event.

**Sprints:** 01 Foundations · 02 Production ground · 03 Accounts · 04 Admin and ingest ·
05 Public catalogue · 06 Stars and downloads · 07 Requests · 08 Beta hardening

**Exit criteria**

- [ ] `https://<domain>` serves the library over a valid certificate, restarts by itself after
      a server reboot, and deploys with one command.
- [ ] A new reader can sign up with a Turkmen phone number, receive a code on screen, log in,
      and stay logged in.
- [ ] An admin can upload a PDF with metadata and see it appear in the public catalogue.
- [ ] A reader can find that book by searching, download it, and see their star balance fall
      by the book's price — with a matching ledger entry.
- [ ] A reader can post a request and any visitor can upvote it.
- [ ] The database is backed up nightly and a restore has been performed at least once.
- [ ] 5-10 invited testers have each completed sign-up → search → download unaided.

**Deliberately not in Phase 1:** real SMS, real payments, the 30 GB import, reading in the
browser, any kind of notification.

---

## Phase 2 — Real codes, real money

**Goal:** remove the two fictions left in Phase 1. Codes arrive by SMS; stars are bought with
mobile operator transfers instead of being granted by hand.

This is the riskiest phase because most of it depends on things outside the code: how the
operator's transfer notifications are actually worded, whether the forwarding app is reliable,
and whether a phone left plugged in for months keeps working. Several research items in
[`04-risks-and-research.md`](04-risks-and-research.md) block this phase and should be answered
*during Phase 1*, not when this phase starts.

**Likely sprints:** OTP delivery over real SMS · forwarder phone and webhook endpoint ·
star packages and the purchase flow · reconciliation, unmatched-payment queue and admin ledger
tools.

**Exit criteria**

- [ ] Someone who is not the developer buys stars by operator transfer and sees their balance
      rise without anyone intervening.
- [ ] Dev-OTP mode is off in production and cannot be enabled by accident.
- [ ] A payment that cannot be matched to a reader lands in an admin queue and is never lost.
- [ ] A duplicate delivery of the same payment SMS credits stars exactly once.
- [ ] The admin can see, for any reader, every star they have ever gained or spent and why.
- [ ] There is an alert if the forwarder phone stops reporting for more than a few hours.

---

## Phase 3 — The collection

**Goal:** get the existing ~30 GB of PDFs into the library without typing thirty thousand
fields by hand, and make sure a catalogue of that size is still navigable.

The approach is semi-automatic ([ADR-0010](adr/0010-semi-automatic-bulk-import.md)): a script
hashes and de-duplicates the files, tries to match each one against Open Library, and files
everything it could not match — which will be most of the Turkmen-language books, since Open
Library barely covers them — into a manual entry queue with the PDF's first page rendered
alongside the form, so filling it in is fast.

Two practical constraints shape this phase: getting 30 GB onto the server takes real time on
a real connection, and 120 GB of disk is a ceiling worth measuring against before the import
rather than after.

**Likely sprints:** ingest pipeline and transport to the server · Open Library matching ·
manual entry queue interface · catalogue at scale (pagination, browse by author and subject,
search quality).

**Exit criteria**

- [ ] The import can be run repeatedly and never creates a duplicate book for a file already in
      the library.
- [ ] Over 1,000 books are live, each with at least a title, an author and a language.
- [ ] The manual entry queue takes well under a minute per book.
- [ ] Disk usage and headroom are visible on an admin page rather than being a surprise.
- [ ] Search still returns a useful first page for a common Turkmen word.

---

## Phase 4 — Requests that cost something

**Goal:** let readers spend stars to prioritise a request, turning the request list from a wish
list into a signal about what people will actually pay to have digitised.

A request that has been paid for is a promise, so this phase needs rules for what happens when
a promise is not kept: an expiry period, and stars returned to the reader if the book is not
added. Without that, the feature is a way to take money for nothing.

**Likely sprints:** spending stars on a request and the resulting ranking · expiry, refunds and
the admin fulfilment queue.

**Exit criteria**

- [ ] A reader can spend stars on a request and see it rise in the ranking.
- [ ] The ranking visibly combines upvotes and stars, and the rule is explained on the page.
- [ ] An unfulfilled priority request expires and refunds automatically, with ledger entries on
      both sides.
- [ ] The admin queue is ordered by what would satisfy the most invested readers first.

---

## Backlog

Not scheduled, not promised. Recorded here so they stop occupying attention. Anything that
graduates from this list becomes a phase with its own exit criteria.

| Idea | Note |
|---|---|
| Reading in the browser | The largest single change to the product, and in tension with the "hands you a file" anti-goal. Would need its own vision revision. |
| A reader's own shelf | Favourites and download history. Cheap, and probably the first thing to graduate. |
| Notify me when this is added | Needs working SMS from Phase 2; closes the loop on requests. |
| Full-text search inside PDFs | Expensive on 2 GB of RAM. Would likely need a separate index and careful memory limits. |
| OCR for scanned books | Prerequisite for the above on scans. Very CPU-hungry; would have to run off the server. |
| EPUB alongside PDF | Much better on phones. Conversion quality for scans is poor, so this suits born-digital books only. |
| Russian-language interface | Depends on whether readers expect it — see R8 in [`04-risks-and-research.md`](04-risks-and-research.md). |
| Series and collections | Grouping multi-volume works, which the flat book model cannot express. |
| Public statistics page | Books, downloads, fulfilled requests. Good for trust, trivial to build. |
