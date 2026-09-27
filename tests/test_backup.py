"""Nightly backups (Sprint 08 task 1, ADR-0020): the copy, the prune, and the Telegram send.

Nothing here reaches the network: `send` is injected, and the multipart body is checked as bytes.
"""
from __future__ import annotations

import email.parser
import email.policy
import sqlite3
import zipfile
from datetime import date, timedelta

import pytest

from app import stars
from app.db import apply_migrations, connect, current_migration_version
from scripts import backup

TODAY = date(2026, 9, 27)


@pytest.fixture()
def source(tmp_path):
    """A migrated WAL database with one reader holding 7 stars, kept open like the live app."""
    path = tmp_path / "live.db"
    conn = connect(path)
    apply_migrations(conn)
    reader = conn.execute("INSERT INTO users (phone) VALUES ('+99361000001')").lastrowid
    conn.commit()
    stars.grant(conn, reader, 7, "Synag")
    yield path, conn
    conn.close()


@pytest.fixture()
def dest(tmp_path):
    return tmp_path / "backups"


def open_copy(path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


# --- The copy --------------------------------------------------------------------------------


def test_rows_still_only_in_the_wal_are_in_the_backup(source, dest):
    path, live = source
    live.execute("INSERT INTO users (phone) VALUES ('+99361000002')")
    live.commit()  # committed to the -wal; the live connection stays open, nothing checkpointed
    assert (path.parent / "live.db-wal").stat().st_size > 0

    result = backup.run(path, dest, 30, TODAY)

    copy = open_copy(result.path)
    assert copy.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 2
    assert stars.totals(copy)["held"] == 7


def test_the_copy_is_one_sound_self_contained_file_already_migrated(source, dest):
    result = backup.run(source[0], dest, 30, TODAY)

    assert result.path.name == "kitaphana-2026-09-27.db"
    copy = open_copy(result.path)
    assert copy.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    assert copy.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    # The sprint's restore test: migrating a restored backup is a no-op.
    before = current_migration_version(copy)
    copy.close()
    restored = connect(result.path)
    assert apply_migrations(restored) == []
    assert current_migration_version(restored) == before


def test_a_same_day_rerun_replaces_the_copy_and_leaves_nothing_behind(source, dest):
    backup.run(source[0], dest, 30, TODAY)
    backup.run(source[0], dest, 30, TODAY)
    assert sorted(path.name for path in dest.iterdir()) == ["kitaphana-2026-09-27.db"]


def test_a_missing_source_fails_and_writes_nothing(tmp_path, dest):
    with pytest.raises(backup.BackupFailed):
        backup.run(tmp_path / "nowhere.db", dest, 30, TODAY)
    assert list(dest.iterdir()) == []


def test_the_caption_describes_the_copy(source, dest):
    caption = backup.run(source[0], dest, 30, TODAY).caption
    assert "2026-09-27" in caption
    assert "1 okyjy" in caption and "7 ýyldyz" in caption
    assert "ok" in caption


# --- Pruning ---------------------------------------------------------------------------------


def _touch(dest, day: date, suffix=".db"):
    dest.mkdir(parents=True, exist_ok=True)
    (dest / f"kitaphana-{day.isoformat()}{suffix}").write_text("x")


def test_prune_keeps_the_window_and_leaves_other_files_alone(source, dest):
    for days_ago in (1, 30, 31, 60):
        _touch(dest, TODAY - timedelta(days=days_ago))
        _touch(dest, TODAY - timedelta(days=days_ago), ".sent")
    (dest / "notes.txt").write_text("mine")

    result = backup.run(source[0], dest, 30, TODAY)

    left = sorted(path.name for path in dest.iterdir())
    assert "kitaphana-2026-08-28.db" in left  # 30 days ago: inside the window
    assert "kitaphana-2026-08-27.db" not in left and "kitaphana-2026-08-27.sent" not in left
    assert "kitaphana-2026-07-29.db" not in left
    assert "notes.txt" in left
    assert len(result.pruned) == 4


def test_prune_never_deletes_the_newest_backup(dest):
    _touch(dest, TODAY - timedelta(days=90))
    assert backup.prune(dest, 30, TODAY) == []
    assert (dest / "kitaphana-2026-06-29.db").exists()


# --- Sending ---------------------------------------------------------------------------------


def test_the_zip_holds_exactly_the_backup_and_is_sent_with_the_caption(source, dest):
    sent = []

    def send(zip_path, caption):
        with zipfile.ZipFile(zip_path) as archive:
            sent.append((zip_path.name, archive.namelist(), archive.read("kitaphana-2026-09-27.db"), caption))

    result = backup.run(source[0], dest, 30, TODAY, send)

    [(name, members, data, caption)] = sent
    assert name == "kitaphana-2026-09-27.zip"
    assert members == ["kitaphana-2026-09-27.db"]
    assert data == result.path.read_bytes()
    assert caption == result.caption
    assert result.sent and (dest / "kitaphana-2026-09-27.sent").exists()


def test_a_failed_send_keeps_the_backup_and_marks_nothing_sent(source, dest):
    def send(zip_path, caption):
        raise backup.BackupFailed("Telegram refused sendDocument: chat not found")

    result = backup.run(source[0], dest, 30, TODAY, send)

    assert result.path.exists()
    assert not result.sent and "chat not found" in result.send_error
    assert not (dest / "kitaphana-2026-09-27.sent").exists()


def test_a_rerun_forgets_the_earlier_send_until_it_sends_again(source, dest):
    backup.run(source[0], dest, 30, TODAY, lambda zip_path, caption: None)
    backup.run(source[0], dest, 30, TODAY)  # no Telegram this time
    assert not (dest / "kitaphana-2026-09-27.sent").exists()


def test_multipart_body_is_well_formed():
    body, content_type = backup.multipart(
        {"chat_id": "12345", "caption": "Ätiýaçlyk ýyldyz"}, "document", "kitaphana-2026-09-27.zip", b"PK\x03\x04data"
    )
    message = email.parser.BytesParser(policy=email.policy.HTTP).parsebytes(
        f"Content-Type: {content_type}\r\n\r\n".encode() + body
    )
    parts = {part.get_param("name", header="content-disposition"): part for part in message.iter_parts()}
    assert parts["chat_id"].get_content().strip() == "12345"
    assert parts["caption"].get_payload(decode=True).decode() == "Ätiýaçlyk ýyldyz"
    document = parts["document"]
    assert document.get_filename() == "kitaphana-2026-09-27.zip"
    assert document.get_payload(decode=True) == b"PK\x03\x04data"


# --- The command -----------------------------------------------------------------------------


def test_main_without_telegram_backs_up_and_sends_nothing(source, test_settings, tmp_path, capsys):
    test_settings(database_path=source[0])
    assert backup.main([]) == 0
    out = capsys.readouterr().out
    assert "Backed up to" in out and "nothing sent" in out
    assert list((tmp_path / "backups").glob("kitaphana-*.db"))


def test_main_fails_loudly_when_the_send_fails(source, test_settings, monkeypatch, capsys):
    test_settings(database_path=source[0], telegram_bot_token="123:abc", telegram_chat_id="42")

    def refuse(token, chat_id):
        def send(zip_path, caption):
            raise backup.BackupFailed("could not reach Telegram: timed out")
        return send

    monkeypatch.setattr(backup, "telegram_sender", refuse)
    assert backup.main([]) == 1
    assert "NOT sent to Telegram" in capsys.readouterr().err


def test_find_chat_needs_a_token(capsys):
    assert backup.main(["--find-chat"]) == 1
    assert "TELEGRAM_BOT_TOKEN" in capsys.readouterr().err
