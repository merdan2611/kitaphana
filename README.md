# Kitaphana

A digital library for books in Turkmen. Readers browse a catalogue, spend **stars** (a
prepaid credit) to download PDFs, and request books that are not in the library yet.

Status: **Sprint 01 shipped** — the skeleton runs locally: a home page, a health check, and a
migrated SQLite database. Nothing user-facing yet; see
[`docs/03-roadmap.md`](docs/03-roadmap.md) for what's next.

## Stack

| Layer | Choice |
|---|---|
| Backend | FastAPI (Python 3.11+) |
| Database | SQLite, WAL mode |
| Frontend | Server-rendered HTML + plain CSS/JS, no framework |
| File storage | Local disk on the VPS |
| Hosting | Turkmentelecom VDS Storage M (2 vCPU, 2 GB RAM, 120 GB SSD) |
| Process / proxy | systemd + nginx, no Docker |
| Accounts | Phone number + SMS OTP |

Each of these is a deliberate decision with a written rationale in [`docs/adr/`](docs/adr/).

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # dev defaults: OTP shown on screen, no real SMS
python -m scripts.migrate     # creates and migrates kitaphana.db
uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000, or check http://127.0.0.1:8000/health.

## Tests

```bash
pytest
```

## Documentation

Start at [`docs/03-roadmap.md`](docs/03-roadmap.md) — it answers "where am I and what is next?".
[`docs/README.md`](docs/README.md) explains which document answers which question.
