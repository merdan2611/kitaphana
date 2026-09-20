# Sprint 08 — Beta hardening

| | |
|---|---|
| **Status** | ⚪ Pending |
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
and memory use. 120 GB is a ceiling and 2 GB of RAM is a tighter one
([ADR-0015](../adr/0015-turkmentelecom-vds-hosting.md)); both should be visible before they are
urgent.

**Done when:** the page shows real figures, and you know today's headroom.

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

`scripts/backup.sh` · `scripts/restore.md` · `templates/404.html` · `templates/500.html` ·
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
[ADR-0015](../adr/0015-turkmentelecom-vds-hosting.md) ·
[`../04-risks-and-research.md`](../04-risks-and-research.md)
