# ADR-0020: Nightly database backups, sent to a private Telegram chat

- **Status**: Accepted
- **Date**: 2026-09-27
- **Supersedes**: [ADR-0011](0011-backup-policy.md)

## Context

[ADR-0011](0011-backup-policy.md) decided what to back up: the database, never the PDFs. It
also decided how: a nightly SQLite backup, a rolling window, and one rehearsed restore. Every
part of that still holds.

What it left weak was getting the copy off the server. It relied on the developer pulling the
backups down "periodically", and admitted that the habit would lapse. A backup that only
exists on the droplet it protects is lost with the droplet, the DigitalOcean account, or the
disk.

Sprint 08 put the site on a real server with real accounts. The developer proposed sending
each night's backup to their own Telegram: it is always on their phone, its storage is
unlimited, and it is run by a company that is not DigitalOcean.

## Decision

**What is backed up is unchanged:** the database, not the PDFs. The PDFs' originals stay on
the developer's machine and external drive.

**Every night at 03:30 (Ashgabat), as the `kitaphana` user** (`scripts/backup.py`, from
`/etc/cron.d/kitaphana-backup`):

1. **Copy.** SQLite's online backup API (`Connection.backup`, the API behind the shell's
   `.backup`) copies the live database, never `cp`, which can tear a WAL database
   ([ADR-0016](0016-sqlite-wal-and-migrations.md)). The copy is switched out of WAL,
   integrity-checked, and only then named `kitaphana-YYYY-MM-DD.db`.
2. **Keep on the server.** `/var/backups/kitaphana` holds 30 days, for a quick restore that
   doesn't need Telegram. The newest copy is never pruned.
3. **Send to Telegram.** The copy is zipped and sent by a bot (Bot API `sendDocument`) to the
   developer's private chat. The caption gives its date, size, reader count, book count and
   stars held, so each night's message can be checked at a glance. A night without a message
   is a failure worth looking into, as is a red mark on the admin overview.
4. **Rehearse a restore.** At least one restore from a Telegram copy happens before Phase 1
   ends, as ADR-0011 required. The procedure is in `scripts/restore.md`.

**The zip is not password-protected.** The developer chose this knowingly on 2026-09-27: a
password that could be forgotten would make every copy useless, at the moment it matters
most.

## Consequences

### Positive

- The copy leaves the server every night without anyone remembering to do it, and lands with
  a second company. That is part of what [R11](../04-risks-and-research.md) was after, for the
  database at least.
- A missing copy is visible twice: no message that morning, and a red mark on the dashboard.
- The copies on the server still allow a restore in a minute with no network needed.

### Negative / accepted costs

- **Anyone with access to the developer's Telegram account can read every reader's phone
  number, star balance and download history.** Telegram's ordinary chats are not end-to-end
  encrypted. This is the cost of the plain zip. It is worth revisiting before real payments
  (Phase 2), when the ledger holds bought stars; encrypting the zip is then a small change.
- **Bots may upload at most 50 MB.** The database is about 100 KB today and grows by
  kilobytes per reader, so this is years away. The script refuses above 49 MB and says so,
  rather than failing silently.
- **Telegram is one more dependency.** If Telegram is unreachable or the bot is blocked, the
  night's copy stays on the server, the script exits with an error in the journal, and the
  dashboard shows it unsent.
- **The bot token is a secret on the server** (`.env`). Anyone holding it can send as the
  bot, but can't read the developer's other chats.
- Up to 24 hours of changes can still be lost, as before.

## Alternatives considered

- **Keep ADR-0011's manual pull to the laptop.** Needs nothing new, and was being skipped
  already. It still works (`rsync` from `/var/backups/kitaphana`) as an extra copy.
- **A password-protected zip.** Protects the phone numbers if the Telegram account is ever
  compromised; offered, and declined for now (see above).
- **Object storage with another provider** (for example S3-compatible storage). The thorough
  answer, and what R11 imagines for the PDFs too. It means another account, bill and
  credentials to look after, for a file of a few hundred kilobytes.
- **DigitalOcean's droplet backups or snapshots** ([R1](../04-risks-and-research.md)). They
  complement this rather than replace it: they don't survive losing the account.
