"""The admin overview's figures (Sprint 08 task 4): activity from the database, and the server."""
from __future__ import annotations

import os
from datetime import datetime, time, timedelta, timezone

import pytest

from app import dashboard
from app.db import apply_migrations, connect, timestamp
from app.templating import ASHGABAT
from tests.test_admin import admin  # noqa: F401  (fixture)

HOUR = timedelta(hours=1)
DAY = timedelta(days=1)


@pytest.fixture()
def conn(db_path):
    conn = connect(db_path)
    apply_migrations(conn)
    try:
        yield conn
    finally:
        conn.close()


def add_user(conn, phone: str, ago: timedelta = timedelta()) -> int:
    return conn.execute(
        "INSERT INTO users (phone, created_at) VALUES (?, ?)", (phone, timestamp(-ago))
    ).lastrowid


def add_session(conn, user_id: int, seen_ago: timedelta, token: str) -> None:
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at, last_seen_at) VALUES (?, ?, ?, ?)",
        (token, user_id, timestamp(DAY * 30), timestamp(-seen_ago)),
    )


def add_book(conn, title: str) -> int:
    return conn.execute(
        "INSERT INTO books (title, author, language, content_hash, file_size) VALUES (?, '', 'tk', ?, ?)",
        (title, title.encode().hex().ljust(64, "0"), 1000),
    ).lastrowid


def add_entry(conn, user_id: int, amount: int, reason: str, book_id: int | None = None,
              at: str | None = None) -> None:
    conn.execute(
        "INSERT INTO star_ledger (user_id, amount, reason, reference, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, reason, f"book:{book_id}" if book_id else None, at or timestamp()),
    )


def add_code(conn, phone: str, used: bool, ago: timedelta = timedelta()) -> None:
    conn.execute(
        "INSERT INTO otp_codes (phone, code_hash, expires_at, used_at, created_at) VALUES (?, 'x', ?, ?, ?)",
        (phone, timestamp(), timestamp(-ago) if used else None, timestamp(-ago)),
    )


# --- Activity --------------------------------------------------------------------------------


def test_active_readers_are_counted_once_however_many_sessions(conn):
    ayna, merdan, old = add_user(conn, "+99361000001"), add_user(conn, "+99361000002"), add_user(conn, "+99361000003")
    add_session(conn, ayna, HOUR, "a1")
    add_session(conn, ayna, 2 * HOUR, "a2")  # a second phone
    add_session(conn, merdan, 3 * DAY, "m1")
    add_session(conn, old, 30 * DAY, "o1")

    figures = dashboard.activity(conn)
    assert figures["active_day"] == 1
    assert figures["active_week"] == 2
    assert figures["readers"] == 3


def test_new_readers_this_week(conn):
    add_user(conn, "+99361000001", 2 * DAY)
    add_user(conn, "+99361000002", 10 * DAY)
    assert dashboard.activity(conn)["readers_new_week"] == 1


def test_every_download_counts_free_re_downloads_included(conn):
    reader = add_user(conn, "+99361000001")
    book = add_book(conn, "Kitap")
    add_entry(conn, reader, 10, "grant")
    add_entry(conn, reader, -5, "spend", book)
    add_entry(conn, reader, 0, "spend", book)  # the free re-download
    add_entry(conn, reader, 0, "spend", book, at=timestamp(-3 * DAY))

    figures = dashboard.activity(conn)
    assert figures["downloads_day"] == 2
    assert figures["downloads_week"] == 3
    assert figures["downloads_total"] == 3


def test_star_totals_add_up_to_the_ledger(conn):
    reader = add_user(conn, "+99361000001")
    book = add_book(conn, "Kitap")
    add_entry(conn, reader, 100, "grant")
    add_entry(conn, reader, -10, "grant")  # an admin correction
    add_entry(conn, reader, -5, "spend", book)

    figures = dashboard.activity(conn)
    assert figures["stars_added"] == 90
    assert figures["stars_spent"] == 5
    assert figures["stars_held"] == 85
    assert figures["stars_added"] - figures["stars_spent"] == figures["stars_held"]


def test_numbers_that_asked_for_a_code_and_never_got_in(conn):
    add_code(conn, "+99361000001", used=False)
    add_code(conn, "+99361000001", used=True)  # got in on the second code: not stuck
    add_code(conn, "+99361000002", used=False)
    add_code(conn, "+99361000002", used=False)  # two tries, still stuck: counted once
    add_code(conn, "+99361000003", used=False, ago=3 * DAY)

    day = dashboard.activity(conn)["logins_day"]
    assert day == {"codes": 4, "sign_ins": 1, "stuck": 1}
    assert dashboard.activity(conn)["logins_week"]["stuck"] == 2


def test_open_requests_come_from_the_request_counts(conn):
    reader = add_user(conn, "+99361000001")
    conn.execute("INSERT INTO requests (user_id, title) VALUES (?, 'Açyk')", (reader,))
    conn.execute(
        "INSERT INTO requests (user_id, title, status, reject_reason, resolved_at)"
        " VALUES (?, 'Ret', 'rejected', 'Boş', ?)",
        (reader, timestamp()),
    )
    figures = dashboard.activity(conn)
    assert figures["requests_open"] == 1
    assert figures["requests_new_week"] == 2


def test_an_empty_database_gives_zeros_not_errors(conn):
    figures = dashboard.activity(conn)
    assert figures["readers"] == 0
    assert figures["stars_held"] == 0
    assert dashboard.top_books(conn) == []
    assert dashboard.newest_readers(conn) == []


# --- The last fourteen days ------------------------------------------------------------------


def _local_midnight_utc() -> datetime:
    today = datetime.now(ASHGABAT).date()
    return datetime.combine(today, time(), ASHGABAT).astimezone(timezone.utc)


def test_days_are_ashgabat_days_not_utc_days(conn):
    reader = add_user(conn, "+99361000001", 30 * DAY)
    midnight = _local_midnight_utc()  # 19:00 UTC the day before
    for moment in (midnight + timedelta(minutes=30), midnight - timedelta(minutes=30)):
        add_entry(conn, reader, 0, "spend", at=moment.strftime("%Y-%m-%d %H:%M:%S"))

    days = dashboard.daily(conn)["downloads"]["days"]
    assert len(days) == 14
    assert days[-1]["label"] == datetime.now(ASHGABAT).strftime("%d.%m")
    assert [days[-2]["value"], days[-1]["value"]] == [1, 1]


def test_each_series_is_scaled_to_its_own_peak(conn):
    reader = add_user(conn, "+99361000001")  # one sign-up today
    for _ in range(4):
        add_entry(conn, reader, 0, "spend")
    add_entry(conn, reader, 0, "spend", at=timestamp(-2 * DAY))

    chart = dashboard.daily(conn)
    downloads, signups = chart["downloads"], chart["signups"]
    assert downloads["total"] == 5 and downloads["peak"] == 4
    assert downloads["days"][-1]["step"] == dashboard.BAR_STEPS
    assert downloads["days"][-3]["step"] == dashboard.BAR_STEPS // 4
    assert signups["days"][-1]["step"] == dashboard.BAR_STEPS  # 1 of 1, not 1 of 4
    assert downloads["days"][0]["step"] == 0


@pytest.mark.parametrize("value, peak, step", [(0, 10, 0), (0, 0, 0), (1, 1000, 1), (10, 10, 20), (5, 10, 10)])
def test_bar_steps(value, peak, step):
    assert dashboard.bar_step(value, peak) == step


# --- Books and readers -----------------------------------------------------------------------


def test_top_books_rank_by_readers_before_downloads(conn):
    one, two = add_user(conn, "+99361000001"), add_user(conn, "+99361000002")
    popular, reread = add_book(conn, "Köp okalan"), add_book(conn, "Gaýta ýüklenen")
    add_entry(conn, one, 0, "spend", popular)
    add_entry(conn, two, 0, "spend", popular)
    for _ in range(3):
        add_entry(conn, one, 0, "spend", reread)

    top = dashboard.top_books(conn)
    assert [(row["title"], row["readers"], row["downloads"]) for row in top] == [
        ("Köp okalan", 2, 2),
        ("Gaýta ýüklenen", 1, 3),
    ]


def test_newest_readers_show_last_seen_and_balance(conn):
    first = add_user(conn, "+99361000001", 2 * DAY)
    latest = add_user(conn, "+99361000002")
    add_session(conn, first, HOUR, "f1")
    add_entry(conn, latest, 7, "grant")

    rows = dashboard.newest_readers(conn)
    assert [row["phone"] for row in rows] == ["+99361000002", "+99361000001"]
    assert rows[0]["last_seen_at"] is None and rows[0]["balance"] == 7
    assert rows[1]["last_seen_at"] is not None and rows[1]["balance"] == 0


# --- The server ------------------------------------------------------------------------------


def test_server_figures_are_real_numbers(conn, db_path, tmp_path):
    figures = dashboard.server(conn, db_path, tmp_path)
    assert figures["disk_total"] > figures["disk_free"] > 0
    assert figures["db_size"] > 0
    assert figures["migration"] is not None
    assert figures["pdf_count"] == 0


def test_server_figures_missing_proc_are_none(conn, db_path, tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard, "PROC", tmp_path / "no-proc")
    figures = dashboard.server(conn, db_path, tmp_path)
    for key in ("memory_total", "memory_available", "app_memory", "app_memory_limit", "uptime_seconds"):
        assert figures[key] is None, key
    assert figures["memory_low"] is False


def _fake_proc(root, meminfo: str, cgroup: str) -> None:
    (root / "self").mkdir(parents=True)
    (root / "meminfo").write_text(meminfo)
    (root / "uptime").write_text("93784.12 180000.00\n")
    (root / "self" / "status").write_text("Name:\tuvicorn\nVmRSS:\t   61440 kB\n")
    (root / "self" / "cgroup").write_text(cgroup)


def test_memory_limit_comes_from_the_service_cgroup(conn, db_path, tmp_path, monkeypatch):
    proc, cgroups = tmp_path / "proc", tmp_path / "cgroup"
    _fake_proc(proc, "MemTotal: 2000000 kB\nMemAvailable: 150000 kB\n", "0::/system.slice/kitaphana.service\n")
    (cgroups / "system.slice" / "kitaphana.service").mkdir(parents=True)
    (cgroups / "system.slice" / "kitaphana.service" / "memory.max").write_text("805306368\n")
    monkeypatch.setattr(dashboard, "PROC", proc)
    monkeypatch.setattr(dashboard, "CGROUP_ROOT", cgroups)

    figures = dashboard.server(conn, db_path, tmp_path)
    assert figures["app_memory"] == 61440 * 1024
    assert figures["app_memory_limit"] == 805306368
    assert figures["memory_available"] == 150000 * 1024
    assert figures["memory_low"] is True  # under 200 MB
    assert figures["uptime_seconds"] == 93784


def test_an_unlimited_cgroup_has_no_limit(conn, db_path, tmp_path, monkeypatch):
    proc, cgroups = tmp_path / "proc", tmp_path / "cgroup"
    _fake_proc(proc, "MemTotal: 2000000 kB\nMemAvailable: 1500000 kB\n", "0::/user.slice\n")
    (cgroups / "user.slice").mkdir(parents=True)
    (cgroups / "user.slice" / "memory.max").write_text("max\n")
    monkeypatch.setattr(dashboard, "PROC", proc)
    monkeypatch.setattr(dashboard, "CGROUP_ROOT", cgroups)

    figures = dashboard.server(conn, db_path, tmp_path)
    assert figures["app_memory_limit"] is None
    assert figures["memory_low"] is False


def test_low_disk_is_flagged(conn, db_path, tmp_path, monkeypatch):
    usage = type("Usage", (), {"total": 50 * 1024**3, "used": 46 * 1024**3, "free": 4 * 1024**3})
    monkeypatch.setattr(dashboard.shutil, "disk_usage", lambda path: usage)
    assert dashboard.server(conn, db_path, tmp_path)["disk_low"] is True


# --- The page --------------------------------------------------------------------------------


def test_admin_overview_shows_the_dashboard(admin, db):  # noqa: F811
    reader = add_user(db, "+99365111222")
    book = add_book(db, "Görogly")
    add_entry(db, reader, 10, "grant")
    add_entry(db, reader, -3, "spend", book)
    db.commit()

    page = admin.get("/admin")
    assert page.status_code == 200
    for text in ("Okyjylar", "Soňky 14 gün", "Girişler", "Serwer", "Iň köp ýüklenen kitaplar", "Görogly"):
        assert text in page.text, text
    assert "/admin/stars?phone=%2B99365111222" in page.text
    assert 'style="' not in page.text  # heights are classes, ready for a strict CSP


# --- Backups ---------------------------------------------------------------------------------


def test_no_backup_folder_is_stale_not_an_error(tmp_path):
    status = dashboard.last_backup(tmp_path / "missing")
    assert status["name"] is None and status["stale"] is True and status["sent"] is False


def test_the_newest_backup_is_reported_with_its_telegram_mark(tmp_path):
    for day in ("2026-09-25", "2026-09-26"):
        (tmp_path / f"kitaphana-{day}.db").write_bytes(b"x" * 10)
    (tmp_path / "kitaphana-2026-09-26.sent").write_text("sent")
    (tmp_path / "notes.db").write_text("not a backup")

    status = dashboard.last_backup(tmp_path)
    assert status["name"] == "kitaphana-2026-09-26.db"
    assert status["size"] == 10
    assert status["sent"] is True
    assert status["stale"] is False  # written just now


def test_an_old_backup_is_stale(tmp_path):
    old = tmp_path / "kitaphana-2026-09-01.db"
    old.write_text("x")
    two_days_ago = datetime.now(timezone.utc).timestamp() - 2 * 86400
    os.utime(old, (two_days_ago, two_days_ago))
    assert dashboard.last_backup(tmp_path)["stale"] is True


def test_admin_overview_warns_when_there_is_no_backup(admin):  # noqa: F811
    page = admin.get("/admin")
    assert "Soňky ätiýaçlyk nusga" in page.text and "Entek ýok" in page.text


def test_a_quiet_fortnight_is_said_in_words_not_drawn_as_an_empty_chart(admin):  # noqa: F811
    page = admin.get("/admin").text
    assert "14 günde ýükleme bolmady." in page
    assert "14 günde täze okyjy bolmady." not in page  # the admin signed up today


def test_book_counts_sit_in_the_top_row_with_drafts_linked(admin, db):  # noqa: F811
    add_book(db, "Neşir edilen")
    db.execute("UPDATE books SET is_published = 1")
    add_book(db, "Garalama kitap")
    db.commit()
    page = admin.get("/admin").text
    top_row = page.split('<dl class="admin-counts dash-counts">', 1)[1].split("</dl>", 1)[0]
    assert "<dt>Kitaplar</dt>" in top_row
    assert "1 neşir edilen" in top_row
    assert '<a href="/admin/books?status=draft">1 garalama</a>' in top_row
