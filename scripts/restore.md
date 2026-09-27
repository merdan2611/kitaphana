# Restoring the database from a backup

The procedure, as rehearsed in Sprint 08 ([ADR-0020](../docs/adr/0020-nightly-backups-to-telegram.md)).
Only the database is restored. PDFs come back by re-uploading them from the originals. Until
they do, their books show but can't be downloaded: the download returns a 404, not a stack
trace.

## Where the copies are

- **Telegram:** each night's `kitaphana-YYYY-MM-DD.zip` in the backup bot's chat. Download it,
  then unzip it to get `kitaphana-YYYY-MM-DD.db`.
- **The server:** `/var/backups/kitaphana/kitaphana-YYYY-MM-DD.db`, 30 days of them, already
  unzipped.

Each copy is a complete, integrity-checked SQLite file, not in WAL mode, with nothing beside
it that it needs.

## Restoring on the server

As root on the droplet. The site is down from the stop to the start, typically under a minute.

```sh
systemctl stop kitaphana

# Keep what is there now, in case the restore is the mistake.
cp -a /var/lib/kitaphana/db/kitaphana.db /var/lib/kitaphana/db/kitaphana.db.before-restore

# The copy: from /var/backups/kitaphana, or uploaded from the laptop with
#   scp kitaphana-YYYY-MM-DD.db root@159.65.8.186:/tmp/
install -o kitaphana -g kitaphana -m 600 /var/backups/kitaphana/kitaphana-YYYY-MM-DD.db \
    /var/lib/kitaphana/db/kitaphana.db
# The old WAL files belong to the database just replaced: left behind, SQLite would try to
# apply them to the restored one.
rm -f /var/lib/kitaphana/db/kitaphana.db-wal /var/lib/kitaphana/db/kitaphana.db-shm

systemctl start kitaphana
curl -s http://127.0.0.1:8000/health      # "status": "ok", and the migration number
```

If the backup predates a migration, `./deploy.sh` (or `sudo -u kitaphana .venv/bin/python -m
scripts.migrate`) brings it up to date. Migrations only go forward.

Afterwards, sign in, open the admin overview, and check a reader or two whose balance you know.
Delete `kitaphana.db.before-restore` once you're satisfied.

## Rehearsing on the laptop

This is how Sprint 08 proved a backup is real, without touching the server:

```sh
cd ~/vs/digital_library
mkdir -p /tmp/restore && unzip -o ~/Downloads/kitaphana-YYYY-MM-DD.zip -d /tmp/restore
export DATABASE_PATH=/tmp/restore/kitaphana-YYYY-MM-DD.db MEDIA_DIR=/tmp/restore/media
.venv/bin/python -m scripts.migrate          # expect: No pending migrations.
.venv/bin/uvicorn app.main:app --port 8010   # then open http://127.0.0.1:8010/health
```

Then compare each reader's balance in the copy with the server's at the time of the backup
(`python -c` with `app.stars.balance`, or the admin's stars page). They must match exactly.
