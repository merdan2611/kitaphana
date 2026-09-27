"""Back up the database, keep a rolling window of copies, and send each one to Telegram
(Sprint 08 task 1, ADR-0020).

Usage (from the project root; on the server it runs nightly from /etc/cron.d/kitaphana-backup):
    python -m scripts.backup
    python -m scripts.backup --find-chat     # once, to learn TELEGRAM_CHAT_ID

The copy is made with SQLite's online backup API (Connection.backup, the API behind the sqlite3
shell's .backup), never by copying the file: the database runs in WAL mode, and a plain copy can
be torn (ADR-0016). The copy is switched out of WAL and integrity-checked before it replaces
anything, so every kitaphana-YYYY-MM-DD.db in the folder is one self-contained, sound file.

Run it as the kitaphana user, never as root. Opening the live database as root while its -wal
and -shm files are absent would create them root-owned, and the app could no longer open its own
database.

Only the database is backed up. The PDFs are not (ADR-0020): they stay on the developer's machine
and external drive, and would not fit through a bot upload anyway.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import tempfile
import urllib.error
import urllib.request
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

from app import config, stars
from app.db import timestamp

BACKUP_NAME = re.compile(r"kitaphana-(\d{4}-\d{2}-\d{2})\.(db|sent)")

# Bots may upload up to 50 MB (Telegram Bot API, sendDocument). Keep clear of the edge.
TELEGRAM_LIMIT = 49 * 1024 * 1024
TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"

Sender = Callable[[Path, str], None]


class BackupFailed(Exception):
    pass


@dataclass
class Result:
    path: Path
    size: int
    caption: str
    sent: bool = False
    send_error: str | None = None
    pruned: list[str] = field(default_factory=list)


# --- The copy --------------------------------------------------------------------------------


def make_copy(source: Path, part: Path) -> None:
    """Copy the live database into `part` and prove the copy sound. Raises BackupFailed."""
    try:
        src = sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True, timeout=30)
    except sqlite3.Error as exc:
        raise BackupFailed(f"cannot open {source}: {exc}") from exc
    try:
        dst = sqlite3.connect(part)
        try:
            src.backup(dst)
            # One self-contained file: no -wal beside it for a restore to lose.
            dst.execute("PRAGMA journal_mode=DELETE")
            check = dst.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            dst.close()
    except sqlite3.Error as exc:
        raise BackupFailed(f"backup of {source} failed: {exc}") from exc
    finally:
        src.close()
    if check != "ok":
        raise BackupFailed(f"the copy failed its integrity check: {check}")


def describe(path: Path, day: date) -> str:
    """The Telegram caption: enough to see at a glance that last night's copy is real."""
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        readers = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        books = conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
        held = stars.totals(conn)["held"]
    finally:
        conn.close()
    size = path.stat().st_size
    return (
        f"Kitaphana: ätiýaçlyk nusga {day.isoformat()}\n"
        f"{size / 1024:.0f} KB · {readers} okyjy · {books} kitap · {held} ýyldyz okyjylarda\n"
        "Bitewilik barlagy: ok"
    )


def prune(dest_dir: Path, keep_days: int, today: date) -> list[str]:
    """Delete backups (and their .sent markers) dated more than `keep_days` before today.

    The newest backup always stays, however old: a server whose cron stopped must not wake up
    and delete its only copy. Files not named like a backup are never touched.
    """
    dated = []
    for path in dest_dir.iterdir():
        match = BACKUP_NAME.fullmatch(path.name)
        if match:
            dated.append((date.fromisoformat(match.group(1)), path))
    backups = [day for day, path in dated if path.suffix == ".db"]
    newest = max(backups, default=None)
    cutoff = today - timedelta(days=keep_days)
    removed = []
    for day, path in sorted(dated):
        if day < cutoff and day != newest:
            path.unlink()
            removed.append(path.name)
    return removed


# --- Telegram --------------------------------------------------------------------------------


def multipart(fields: dict[str, str], file_field: str, filename: str, data: bytes) -> tuple[bytes, str]:
    """A multipart/form-data body and its Content-Type, for one file and some text fields."""
    boundary = uuid.uuid4().hex
    parts = []
    for name, value in fields.items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
        )
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'
        "Content-Type: application/zip\r\n\r\n".encode()
    )
    parts.append(data)
    parts.append(f"\r\n--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _call(token: str, method: str, body: bytes | None = None, content_type: str | None = None) -> dict:
    """One Bot API call. Errors never include the URL: it carries the token."""
    request = urllib.request.Request(TELEGRAM_API.format(token=token, method=method), data=body)
    if content_type:
        request.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            reply = json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            reply = json.load(exc)
        except ValueError:
            raise BackupFailed(f"Telegram answered HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise BackupFailed(f"could not reach Telegram: {getattr(exc, 'reason', exc)}") from None
    if not reply.get("ok"):
        raise BackupFailed(f"Telegram refused {method}: {reply.get('description', 'no reason given')}")
    return reply


def telegram_sender(token: str, chat_id: str) -> Sender:
    def send(zip_path: Path, caption: str) -> None:
        body, content_type = multipart(
            {"chat_id": chat_id, "caption": caption}, "document", zip_path.name, zip_path.read_bytes()
        )
        _call(token, "sendDocument", body, content_type)

    return send


def find_chat(token: str) -> int:
    """Print the chats that have written to the bot, so TELEGRAM_CHAT_ID can be set."""
    updates = _call(token, "getUpdates")["result"]
    chats = {}
    for update in updates:
        message = update.get("message") or update.get("channel_post") or {}
        chat = message.get("chat")
        if chat:
            chats[chat["id"]] = chat
    if not chats:
        print("No messages yet. Open the bot in Telegram, press Start, then run this again.")
        return 1
    for chat_id, chat in chats.items():
        who = chat.get("username") or chat.get("first_name") or chat.get("title") or ""
        print(f"TELEGRAM_CHAT_ID={chat_id}    ({chat.get('type')}: {who})")
    return 0


# --- The whole run ---------------------------------------------------------------------------


def run(source: Path, dest_dir: Path, keep_days: int, today: date, send: Sender | None = None) -> Result:
    """Back up, prune, then send. Raises BackupFailed if no sound copy could be made.

    A failed send does not raise: the copy on disk still stands, and the result says why the
    send failed, so the caller can exit non-zero.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = f"kitaphana-{today.isoformat()}.db"
    final, part = dest_dir / name, dest_dir / f".{name}.part"
    marker = final.with_suffix(".sent")
    try:
        make_copy(source, part)
    except BaseException:
        part.unlink(missing_ok=True)
        raise
    os.replace(part, final)
    marker.unlink(missing_ok=True)  # a re-run's copy has not been sent yet

    result = Result(path=final, size=final.stat().st_size, caption=describe(final, today))
    result.pruned = prune(dest_dir, keep_days, today)

    if send is not None:
        with tempfile.TemporaryDirectory() as scratch:
            zip_path = Path(scratch) / final.with_suffix(".zip").name
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.write(final, final.name)
            try:
                if zip_path.stat().st_size > TELEGRAM_LIMIT:
                    raise BackupFailed(
                        f"the zip is {zip_path.stat().st_size // 1024**2} MB, over the bot upload limit"
                    )
                send(zip_path, result.caption)
            except Exception as exc:  # whatever went wrong, the copy on disk stands
                result.send_error = str(exc) or type(exc).__name__
            else:
                marker.write_text(timestamp() + "\n")
                result.sent = True
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--find-chat", action="store_true", help="print the chat ids that wrote to the bot")
    args = parser.parse_args(argv)
    settings = config.settings
    token, chat_id = settings.telegram_bot_token, settings.telegram_chat_id

    if args.find_chat:
        if not token:
            print("Set TELEGRAM_BOT_TOKEN in .env first.", file=sys.stderr)
            return 1
        try:
            return find_chat(token)
        except BackupFailed as exc:
            print(exc, file=sys.stderr)
            return 1

    send = telegram_sender(token, chat_id) if token and chat_id else None
    try:
        result = run(settings.database_path, settings.backup_dir, settings.backup_keep_days, date.today(), send)
    except BackupFailed as exc:
        print(f"Backup FAILED: {exc}", file=sys.stderr)
        return 1

    pruned = f", pruned {len(result.pruned)}" if result.pruned else ""
    print(f"Backed up to {result.path} ({result.size / 1024:.0f} KB, integrity ok{pruned}).")
    if send is None:
        print("Telegram is not configured (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID): nothing sent.")
    elif result.sent:
        print("Sent to Telegram.")
    else:
        print(f"NOT sent to Telegram: {result.send_error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
