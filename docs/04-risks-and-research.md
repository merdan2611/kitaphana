# Risks and open questions

Things that are not yet known, and things that could go wrong. They live here rather than
inside sprint task lists, because an unanswered question dressed up as a task looks like
development work and gets estimated like development work, then quietly consumes a sprint.

Most research items need nothing but a browser, a phone, or one command on the server. Do them
in the dead time between sprints. Several of them **block Phase 2**, and finding that out
during Phase 2 would be expensive — answer those during Phase 1.

## Open questions

| | Question | Why it matters | Answer by |
|---|---|---|---|
| **R1** | Are DigitalOcean's paid droplet backups or manual snapshots worth adding on top of [ADR-0011](adr/0011-backup-policy.md)'s nightly database pull, and at today's prices? | Snapshots would make rebuilding the whole server minutes instead of an evening; the database backup still has to live off DigitalOcean either way. The question is no longer *whether* the provider offers them ([ADR-0019](adr/0019-digitalocean-droplet-hosting.md)) but whether they are worth the money. | Sprint 08 |
| **R2** | Which Android SMS-forwarding app is actually reliable for months at a time — and can the same app *send* an SMS on request? | If one app can both receive payment notifications and send OTP codes, Phase 2 needs one device instead of a device plus an SMS gateway. This is the single highest-value question on this list. | Before Phase 2 |
| **R3** | What does an incoming operator-transfer SMS actually look like — exact wording, sender ID, and above all: does it contain the paying number? | The entire payment design assumes the payer's number is in the message ([ADR-0008](adr/0008-sms-forwarding-payment-detection.md)). If it is not, Phase 2 needs a different design, probably a reference code the payer has to include. **Blocks Phase 2.** Answer it by sending yourself a small transfer. | Before Phase 2 |
| **R4** | From inside Turkmenistan: does a foreign-registrar domain resolve, and how fast is an 80 MB download from the droplet? **Partly answered 2026-09-25:** the Singapore droplet loads from inside Turkmenistan. | The server is abroad ([ADR-0019](adr/0019-digitalocean-droplet-hosting.md)). Slowness is the accepted cost, but it should be a measured number, not a guess. Port 80 is open on a droplet, so Let's Encrypt's HTTP challenge works. | Sprint 02 |
| **R5** | What upload throughput does the developer's machine get to the droplet, and how long would 30 GB actually take? | Determines whether Phase 3's import is an overnight job or a three-week background chore, and whether it should run in batches. | Before Phase 3 |
| **R6** | How much disk does the existing collection need after de-duplication, and what is the growth rate? | The droplet has 50 GB. The answer decides whether a Block Storage volume for `MEDIA_DIR`, or a bigger droplet, is added before the import ([ADR-0019](adr/0019-digitalocean-droplet-hosting.md)). Better to find out the collection is 45 GB before the import than during it. | Before Phase 3 |
| **R7** | What should a star cost in TMT, and what fees or minimums apply to operator transfers? | Sets the package sizes and whether small purchases are viable at all. | Before Phase 2 |
| **R8** | Do the intended readers expect a Russian interface, or is Turkmen alone sufficient? | Retrofitting a second language after the interface is written costs several times what building for two costs. Ask actual testers in Sprint 08. | Sprint 08 |
| **R9** | What is the legal and practical position on redistributing these scans in Turkmenistan? | Affects what can be hosted, whether authors and publishers should be approached, and what a takedown process should look like. Not a blocker for building, but it should be a considered position rather than an unexamined one. | Before public launch |
| **R10** | How do readers actually search? In particular: do they type Russian titles in Latin letters ("kashtanka" for «Каштанка»), and do they expect titles sorted in Turkmen alphabetical order (… E, Ä, F …) rather than with Ä filed under A? | Sprint 05's search ignores diacritics and case but does not transliterate between scripts, and its title sort files Ä with A. Either could quietly hide books from readers. Watch what testers type and ask them. | Sprint 08 |
| **R11** | If the droplet becomes unreachable from Turkmenistan, or DigitalOcean is lost, how does the library move to another server quickly without losing accounts and star balances? | Postponed on 2026-09-25 until it is actually needed. The idea discussed: keep SQLite, but keep a continuously updated copy of the database (and the PDFs) with a different company, and make rebuilding the server one script. Would replace [ADR-0011](adr/0011-backup-policy.md) with a new ADR when taken up. | When needed; at the latest before real payments (Phase 2) |

When one of these is answered, replace the row with the answer and its date, and update any
ADR it affects.

## Risks

| Risk | If it happens | What reduces it |
|---|---|---|
| **The forwarder phone stops forwarding** — battery, crashed app, network, someone unplugs it | Payments silently stop crediting. Readers pay and get nothing, which is the worst failure this project has. | A heartbeat from the phone and an alert when it goes quiet for a few hours; an admin page showing recent payments so silence is visible; the unmatched-payment queue so nothing is lost when it recovers. |
| **One server, no redundancy** | The whole library is offline until it comes back. | Accepted — [ADR-0019](adr/0019-digitalocean-droplet-hosting.md). The mitigation is not a second server but being able to rebuild quickly: keep the deploy documented, and keep backups off the server. |
| **The server stops being reachable from Turkmenistan** | It works today, but a foreign address range can be filtered at any time, and then readers cannot reach the library at all. | Be ready to move rather than hope: keep copies of the data off the droplet so a new server elsewhere can be running within hours. A droplet snapshot can be restored in another region in minutes, and nothing in the stack is tied to DigitalOcean, so moving to a local server later is replaying the Sprint 02 notes — [ADR-0019](adr/0019-digitalocean-droplet-hosting.md). |
| **The card paying for the droplet stops working** | DigitalOcean suspends the droplet after unpaid invoices, and the library goes offline. | Keep the billing email somewhere it is read, keep a little prepaid credit on the account, and keep backups off DigitalOcean so a lost account is not a lost library. |
| **The database is lost** | Accounts and paid-for star balances are gone. PDFs survive because the originals are on the developer's machine; balances have no second copy anywhere. | Nightly backups pulled off the server, and one rehearsed restore ([ADR-0011](adr/0011-backup-policy.md)). Untested backups do not count. |
| **Disk fills up** | Uploads fail, and SQLite behaves badly with no space for its write-ahead log. | Disk headroom on an admin page from Sprint 08; answer R6 before the bulk import. |
| **2 GB of RAM is not enough under load** | The server starts killing processes; the site goes down at exactly the moment people are using it. | nginx serves all large files ([ADR-0014](adr/0014-x-accel-redirect-for-downloads.md)); few uvicorn workers; no in-process caching of file contents; watch memory during the Sprint 08 test. |
| **Someone scripts the download endpoint** | Bandwidth and stars are drained; at worst the whole collection is mirrored. | Stars make bulk downloading cost money, which is much of why they exist; per-account rate limits; never expose a guessable direct path to a file. |
| **OTP costs are abused** | Once SMS is real, an attacker requesting thousands of codes spends the project's money. | Rate limits per phone number and per IP address, built in Sprint 03 while codes are still free, not retrofitted in Phase 2 when they are not. |
| **Solo developer, no cover** | Everything stops during an illness, an exam period, or a hard month of night shifts. | Accepted, and the reason these documents exist: they are what lets work resume after a gap. Keep the roadmap current — that is the recovery mechanism. |
| **Nobody comes** | The library works and is empty of readers. | The request list is the early signal: if requests appear, there is demand. Phase 3 exists because a catalogue with a thousand books is a different proposition from one with twenty. |
