# Sprint 08 — Beta hardening

| | |
|---|---|
| **Status** | 🟡 In progress (started 2026-09-27) |
| **Phase** | 1 (usable library, codes on screen) |
| **Milestone** | M8 — Testers can use it |
| **Estimated time** | ~1-2 weeks |
| **Depends on** | Sprints 01-07 |

## Goal

Everything works. This sprint is about what happens when it does not: backups that have actually
been restored, errors that are visible, and a site that fails in a way a reader can understand.
Then hand it to real people and find out what is wrong with it.

Phase 1 ends here.

## You can now…

…send the link to someone who is not you, and not need to be there when they open it.

## Tasks

### 1. Database backups — and a restore you have performed

A nightly cron job running `sqlite3 kitaphana.db ".backup /srv/backups/kitaphana-$(date +%F).db"`.
The `.backup` command specifically, not `cp` — copying a live SQLite file in WAL mode can
capture a torn database ([ADR-0011](../adr/0011-backup-policy.md),
[ADR-0016](../adr/0016-sqlite-wal-and-migrations.md)). Prune to a rolling window so backups
cannot fill the disk, and pull them down to the laptop.

Then **restore one into a local copy of the application and open it.** An untested backup is an
assumption. This is the single most important task in the sprint, and the one easiest to mark
done without doing.

**Done when:** a backup from the server has been restored locally, the site runs against it, and
the star balances in it are correct.

> **2026-09-27:** built as `scripts/backup.py` rather than a shell script: Python's
> `Connection.backup` is the same online-backup API as `.backup`, the laptop has no `sqlite3`
> CLI, and the Python version is tested (`tests/test_backup.py`). It runs nightly at 03:30 as
> the `kitaphana` user from `deploy/cron-kitaphana-backup`. It keeps 30 days in
> `/var/backups/kitaphana` and, instead of a manual pull to the laptop, sends each night's
> copy as a zip to the developer's private Telegram chat
> ([ADR-0020](../adr/0020-nightly-backups-to-telegram.md), superseding ADR-0011). The admin
> overview shows the newest backup and whether it reached Telegram. The restore procedure is
> in `scripts/restore.md`.
>
> **2026-09-28, restore rehearsed.** The first backup (104 KB, integrity ok) reached the
> developer's Telegram. That same copy, restored on the laptop: `scripts.migrate` said "No
> pending migrations"; `/health` answered migration 6; the catalogue and requests pages
> served. Its 3 readers, 2 books and 1 request, and every reader's balance (900, 95, 95),
> matched the live database at the time of the backup exactly. Still to see: the first
> unattended 03:30 run, in `journalctl -t kitaphana-backup` and in Telegram.

### 2. Error pages and error visibility

Real 404 and 500 pages in the site's layout. **Debug mode off in production** — no stack trace
should ever reach a reader. Unhandled exceptions log a traceback with enough context to find the
request, and there is a documented way to look: `journalctl -u kitaphana -p err`.

**Done when:** a deliberately broken URL returns a styled 500 with no internals, and the
traceback is findable in the journal within seconds.

### 3. Security pass

Go through it once, deliberately:

- The production secret key is long, random, and not the example value.
- Security headers in nginx: HSTS, `X-Content-Type-Options`, a restrictive referrer policy, and
  a content security policy strict enough to be worth having.
- **Dev-OTP mode off**, verified by attempting a login and seeing no code — not by reading the
  configuration file ([ADR-0013](../adr/0013-dev-otp-mode.md)). It stays off for testers only if
  you have decided Phase 1 testing is over; if testers still need it, this check moves to Phase 2
  and the banner stays.
- Admin URLs return 404 to a normal reader, including every handler, not only the pages.
- The media directory is unreachable by direct URL.
- Session cookies are `Secure`, `HttpOnly`, `SameSite`.
- Rate limits from Sprints 03, 06 and 07 all still fire.

**Done when:** every item has been checked by hand against the live server and the results are
noted in this document.

### 4. Disk and memory visibility

An admin page showing disk usage and free space, database size, book count, total media size,
and memory use. The droplet's 50 GB disk is a ceiling and 2 GB of RAM is a tighter one
([ADR-0019](../adr/0019-digitalocean-droplet-hosting.md)); both should be visible before they are
urgent.

**Done when:** the page shows real figures, and you know today's headroom.

> **2026-09-27:** built as the admin overview itself (`/admin`, "Umumy") rather than a separate
> `system.html`: the admin tab bar is full (ADR-0018). Widened, at the developer's request, into
> a dashboard of what the app already records: readers, active readers, sign-ins and numbers
> that got a code but never got in, downloads, stars, requests, the last 14 days, the most
> downloaded books, and recent ledger activity, beside the disk, memory and database figures.
> Queries live in `app/dashboard.py`; ledger reads stay in `app/stars.py`. **Visits are not
> counted**: page views exist only in nginx's log, which the sandboxed app cannot read, and
> parsing it on each load would slow as it grows. Visit statistics wait for Phase 2 — for
> example a nightly GoAccess report run outside the app.

### 5. Tune the workers

With something real to measure, set the uvicorn worker count for 2 GB of RAM. Start low. Watch
memory during concurrent downloads and confirm that nginx, not the application, is doing the
transferring ([ADR-0014](../adr/0014-x-accel-redirect-for-downloads.md)).

**Done when:** several simultaneous large downloads leave the site responsive and memory stable.

### 6. End-to-end pass on a real device

On an actual phone on mobile data, as a new user: sign up, search, open a book, download it,
post a request, upvote another, check the balance and history. Write down every moment of
friction, however small.

**Done when:** the whole loop completes on a phone and the friction list exists.

### 7. Answer R1 and R8

While in the server panel, check whether snapshots are offered and at what price (R1). While
talking to testers, ask whether they expect a Russian interface (R8) — retrofitting a second
language later costs several times what building for two would.

**Done when:** both are answered and dated in
[`../04-risks-and-research.md`](../04-risks-and-research.md).

### 8. Invite testers

Five to ten people. Give them stars by grant, tell them plainly that codes appear on screen and
the site is invite-only, and watch what they do without helping. The interesting failure is not
someone who cannot sign up — it is someone who finds a book, wants it, and does not finish the
download.

**Done when:** at least five people have completed sign-up → search → download unaided, and
their difficulties are written down.

### 9. Close the phase

Update [`../03-roadmap.md`](../03-roadmap.md): mark Sprint 08 shipped, add the shipped log
entries, and set the current-sprint block to the first Phase 2 sprint. Revisit
[`../02-phases.md`](../02-phases.md) — Phase 2's shape should now be informed by eight sprints of
knowing how long things actually take. Write the Phase 2 sprint documents.

**Done when:** the roadmap describes reality, and a session opening cold can tell where the
project is.

## Done when (sprint acceptance)

- [ ] Backups run nightly, are pulled off the server, and **one has been restored**.
- [ ] No stack trace is reachable by a reader; errors are findable in the journal.
- [ ] The security checklist has been walked and recorded.
- [ ] Disk and memory are visible on an admin page.
- [ ] Concurrent large downloads leave the site responsive.
- [ ] Five or more testers have completed the loop unaided.
- [ ] R1 and R8 are answered.
- [ ] The roadmap points at Phase 2.

## Tests

- Automated: the whole suite from Sprints 01-07 passes against a clean database.
- A restore test: apply migrations to a restored backup and confirm it is a no-op — the backup
  is already current.
- Manual: the security checklist in task 3, item by item, against production.
- Manual: reboot the server once more and confirm everything comes back, including the cron job.

## Files this sprint creates / touches

`scripts/backup.py` · `deploy/cron-kitaphana-backup` · `scripts/restore.md` · `templates/404.html` · `templates/500.html` ·
`templates/admin/system.html` · `deploy/nginx-kitaphana.conf` (security headers) ·
`deploy/kitaphana.service` (workers) · `../03-roadmap.md` · `../02-phases.md`

## No-gos

- No new reader-facing features. Anything the testers ask for goes on a list for Phase 2, not
  into this sprint.
- No real SMS, no payments — Phase 2, even if a tester asks.
- No monitoring stack. A cron job and the journal are enough at this size.
- No public launch. Phase 1 ends invite-only by design, because codes on screen mean anyone who
  knows a phone number can sign in as it.
- No performance work beyond the worker count.

## References

[ADR-0011](../adr/0011-backup-policy.md) ·
[ADR-0013](../adr/0013-dev-otp-mode.md) ·
[ADR-0014](../adr/0014-x-accel-redirect-for-downloads.md) ·
[ADR-0019](../adr/0019-digitalocean-droplet-hosting.md) ·
[`../04-risks-and-research.md`](../04-risks-and-research.md)
