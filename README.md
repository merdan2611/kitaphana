# Kitaphana

A digital library for books in Turkmen. Readers browse a catalogue, spend **stars** (a
prepaid credit) to download PDFs, and request books that are not in the library yet.

Status: **Sprint 05 shipped** — runs locally with phone-number login (the code is shown on
screen while `DEV_OTP_MODE` is on), an admin panel for uploading and publishing books, and a
public catalogue with search at `/books`. See [`docs/03-roadmap.md`](docs/03-roadmap.md) for
what's next.

## Stack

| Layer | Choice |
|---|---|
| Backend | FastAPI (Python 3.11+) |
| Database | SQLite, WAL mode |
| Frontend | Server-rendered HTML + plain CSS/JS, no framework |
| File storage | Local disk on the VPS |
| Hosting | DigitalOcean droplet, Frankfurt (2 GB RAM, 50 GB SSD) |
| Process / proxy | systemd + nginx, no Docker |
| Accounts | Phone number + SMS OTP |

Each of these is a deliberate decision with a written rationale in [`docs/adr/`](docs/adr/).

## Quick start

```bash
# System package for rendering book covers (Fedora: dnf, Debian/Ubuntu: apt)
sudo dnf install poppler-utils

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # dev defaults: OTP shown on screen, no real SMS
python -m scripts.migrate     # creates and migrates kitaphana.db (always use this, not the
                              # sqlite3 CLI: migration 004 calls a Python function)
python -m scripts.seed_fixtures  # optional: five public-domain placeholder books
uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000, or check http://127.0.0.1:8000/health. Keep
`DOWNLOADS_VIA_NGINX=false` in a local `.env`: without nginx in front, a download would
otherwise arrive as an empty file (ADR-0014). Use `localhost` or
`127.0.0.1` rather than a LAN address: the session cookie is `Secure`, and browsers accept that
over plain HTTP only for those two.

To make yourself an admin, log in once, then:

```bash
python -m scripts.make_admin "+993 61 234567"
```

The admin panel is at http://127.0.0.1:8000/admin (a 404 for anyone who is not an admin).
Stars are granted at http://127.0.0.1:8000/admin/stars. Ledger rows can never be deleted, so
try things out on a throwaway `DATABASE_PATH` rather than a database you want to keep clean.

## Tests

```bash
pytest
```

## Documentation

Start at [`docs/03-roadmap.md`](docs/03-roadmap.md) — it answers "where am I and what is next?".
[`docs/README.md`](docs/README.md) explains which document answers which question.
