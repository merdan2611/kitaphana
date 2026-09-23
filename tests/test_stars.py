"""The star ledger (Sprint 06, ADR-0007): the invariants, admin grants and the history page."""
from __future__ import annotations

import re
import sqlite3
import threading
import time

import pytest

from app import stars
from app.config import BASE_DIR
from app.db import connect
from tests.test_auth import PHONE, login

OTHER_PHONE = "+99365111222"


def user_id(db, phone=PHONE) -> int:
    db.execute("INSERT OR IGNORE INTO users (phone) VALUES (?)", (phone,))
    db.commit()
    return db.execute("SELECT id FROM users WHERE phone = ?", (phone,)).fetchone()["id"]


def append(db, uid, amount, reason, reference=None, note=None):
    with stars.transaction(db):
        return stars.append_entry(db, uid, amount, reason, reference, note)


def rows(db, uid=None):
    sql = "SELECT * FROM star_ledger" + (" WHERE user_id = ?" if uid else "") + " ORDER BY id"
    return db.execute(sql, (uid,) if uid else ()).fetchall()


@pytest.fixture()
def admin(client, db):
    login(client)
    db.execute("UPDATE users SET is_admin = 1 WHERE phone = ?", (PHONE,))
    db.commit()
    return client


def header_balance(html: str) -> int:
    match = re.search(r'class="star-balance".*?Ýyldyz balansyňyz: </span>(-?\d+)</span>', html, flags=re.S)
    assert match, "a signed-in page should show the star balance in the header"
    return int(match.group(1))


# --- Arithmetic ------------------------------------------------------------------------------


def test_balance_is_the_sum_of_entries(db):
    uid = user_id(db)
    assert stars.balance(db, uid) == 0
    stars.grant(db, uid, 10, "Hoş geldiňiz")
    append(db, uid, -3, "spend", "book:1", "Görogly")
    append(db, uid, 3, "refund", "book:1", "Faýl açylmady")
    append(db, uid, -4, "spend", "book:2", "Älem")
    assert stars.balance(db, uid) == 6
    assert [row["amount"] for row in rows(db, uid)] == [10, -3, 3, -4]


def test_balances_are_per_reader(db):
    first, second = user_id(db), user_id(db, OTHER_PHONE)
    stars.grant(db, first, 5, "a")
    stars.grant(db, second, 2, "b")
    assert (stars.balance(db, first), stars.balance(db, second)) == (5, 2)


def test_an_insufficient_spend_is_refused_and_writes_no_row(db):
    uid = user_id(db)
    stars.grant(db, uid, 2, "a")
    with pytest.raises(stars.InsufficientStars) as caught:
        append(db, uid, -3, "spend", "book:1", "Görogly")
    assert (caught.value.balance, caught.value.needed) == (2, 3)
    assert len(rows(db, uid)) == 1
    assert stars.balance(db, uid) == 2


def test_a_spend_of_exactly_the_balance_leaves_zero(db):
    uid = user_id(db)
    stars.grant(db, uid, 3, "a")
    append(db, uid, -3, "spend", "book:1", "Görogly")
    assert stars.balance(db, uid) == 0


def test_a_correction_cannot_take_a_balance_below_zero(db):
    uid = user_id(db)
    stars.grant(db, uid, 2, "a")
    with pytest.raises(stars.InsufficientStars):
        stars.grant(db, uid, -3, "ýalňyşlyk")
    stars.grant(db, uid, -2, "ýalňyşlyk")
    assert stars.balance(db, uid) == 0
    assert [row["amount"] for row in rows(db, uid)] == [2, -2]


def test_a_free_download_is_a_zero_spend(db):
    uid = user_id(db)
    append(db, uid, 0, "spend", "book:1", "Mugt kitap")
    assert stars.balance(db, uid) == 0
    assert stars.has_downloaded(db, uid, 1)
    assert not stars.has_paid_for(db, uid, 1)


def test_paid_for_until_refunded(db):
    uid = user_id(db)
    stars.grant(db, uid, 10, "a")
    append(db, uid, -3, "spend", "book:7", "Görogly")
    assert stars.has_paid_for(db, uid, 7)
    assert not stars.has_paid_for(db, uid, 8)
    append(db, uid, 3, "refund", "book:7", "Faýl bozuk")
    assert not stars.has_paid_for(db, uid, 7)


# --- The rules the ledger rests on -----------------------------------------------------------


@pytest.mark.parametrize(
    "amount, reason, reference, note",
    [
        (0, "grant", None, "nothing"),
        (5, "grant", None, None),
        (5, "grant", None, "   "),
        (1, "spend", "book:1", "x"),
        (-1, "refund", "book:1", "x"),
        (0, "topup", "pay:1", None),
        (-2, "spend", None, "x"),
        (2, "refund", None, "x"),
        (2, "gift", None, "x"),
        (True, "grant", None, "x"),
        (1.5, "grant", None, "x"),
    ],
)
def test_malformed_entries_are_refused(db, amount, reason, reference, note):
    uid = user_id(db)
    stars.grant(db, uid, 10, "a")
    with pytest.raises(ValueError):
        append(db, uid, amount, reason, reference, note)
    assert len(rows(db, uid)) == 1


def test_append_entry_only_works_inside_a_ledger_transaction(db):
    uid = user_id(db)
    with pytest.raises(RuntimeError):
        stars.append_entry(db, uid, 5, "grant", note="a")
    assert rows(db, uid) == []


def test_a_ledger_transaction_will_not_swallow_other_uncommitted_work(db):
    uid = user_id(db)
    db.execute("UPDATE users SET is_admin = 1 WHERE id = ?", (uid,))  # opens a transaction
    with pytest.raises(RuntimeError):
        with stars.transaction(db):
            pass
    db.rollback()


def test_an_error_inside_the_transaction_writes_nothing(db):
    uid = user_id(db)
    with pytest.raises(ZeroDivisionError):
        with stars.transaction(db):
            stars.append_entry(db, uid, 5, "grant", note="a")
            1 / 0
    assert rows(db, uid) == []
    assert not db.in_transaction


def test_the_database_refuses_updates_and_deletes(db):
    uid = user_id(db)
    stars.grant(db, uid, 5, "a")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        db.execute("UPDATE star_ledger SET amount = 500")
    db.rollback()
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        db.execute("DELETE FROM star_ledger")
    db.rollback()
    assert [row["amount"] for row in rows(db, uid)] == [5]


def test_the_database_refuses_entries_with_the_wrong_sign(db):
    uid = user_id(db)
    for amount, reason in [(3, "spend"), (0, "grant"), (-1, "refund"), (0, "topup")]:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO star_ledger (user_id, amount, reason, reference) VALUES (?, ?, ?, 'x:1')",
                (uid, amount, reason),
            )
    db.rollback()


def test_a_reader_with_history_cannot_be_deleted(db):
    uid = user_id(db)
    stars.grant(db, uid, 5, "a")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("DELETE FROM users WHERE id = ?", (uid,))
    db.rollback()


def test_no_other_module_touches_the_ledger_table():
    """Task 2: every read and write of star_ledger goes through app/stars.py."""
    offenders = [
        str(path.relative_to(BASE_DIR))
        for folder in ("app", "scripts", "templates")
        for path in (BASE_DIR / folder).rglob("*")
        if path.is_file() and path.suffix in {".py", ".html"} and path.name != "stars.py"
        and "star_ledger" in path.read_text()
    ]
    assert offenders == []


# --- Concurrency -----------------------------------------------------------------------------


def test_two_simultaneous_spends_cannot_overdraw(db, db_path):
    """Stars for one spend, two spends at the same moment: exactly one of them succeeds."""
    uid = user_id(db)
    stars.grant(db, uid, 3, "a")
    barrier = threading.Barrier(2)
    results: list[str] = []

    def spend():
        conn = connect(db_path)
        try:
            barrier.wait()
            with stars.transaction(conn):
                time.sleep(0.05)  # widen the window in which the other thread could slip in
                stars.append_entry(conn, uid, -3, "spend", "book:1", "Görogly")
            results.append("ok")
        except stars.InsufficientStars:
            results.append("refused")
        finally:
            conn.close()

    threads = [threading.Thread(target=spend) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(results) == ["ok", "refused"]
    assert stars.balance(db, uid) == 0
    assert len([row for row in rows(db, uid) if row["reason"] == "spend"]) == 1


# --- Admin grants ----------------------------------------------------------------------------


@pytest.mark.parametrize("method", ["get", "post"])
def test_grant_page_is_404_for_readers(client, method):
    login(client)
    assert getattr(client, method)("/admin/stars", follow_redirects=False).status_code == 404


def test_admin_grants_stars_with_a_note(admin, db):
    reader = user_id(db, OTHER_PHONE)
    response = admin.post(
        "/admin/stars",
        data={"phone": "8 65 111222", "amount": "10", "note": "Synagçy bonusy"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/stars?phone=%2B99365111222&notice=granted"

    [row] = rows(db, reader)
    assert (row["amount"], row["reason"], row["note"], row["reference"]) == (10, "grant", "Synagçy bonusy", None)
    assert stars.balance(db, reader) == 10

    page = admin.get(response.headers["location"]).text
    assert "Ýazgy goşuldy" in page
    assert "Balansy: <strong>10 ýyldyz</strong>" in page
    assert "Synagçy bonusy" in page


def test_a_negative_grant_is_a_new_correcting_row(admin, db):
    reader = user_id(db, OTHER_PHONE)
    stars.grant(db, reader, 10, "Bonus")
    response = admin.post(
        "/admin/stars",
        data={"phone": OTHER_PHONE, "amount": "-4", "note": "Artyk berlipdi"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert [row["amount"] for row in rows(db, reader)] == [10, -4]
    assert stars.balance(db, reader) == 6


def test_a_correction_beyond_the_balance_is_refused(admin, db):
    reader = user_id(db, OTHER_PHONE)
    stars.grant(db, reader, 2, "Bonus")
    response = admin.post("/admin/stars", data={"phone": OTHER_PHONE, "amount": "-5", "note": "x"})
    assert response.status_code == 400
    assert "Okyjynyň balansy 2 ýyldyz" in response.text
    assert len(rows(db, reader)) == 1


@pytest.mark.parametrize(
    "form, field_error",
    [
        ({"phone": "+99365999999", "amount": "5", "note": "x"}, "Bu belgi bilen hasap ýok"),
        ({"phone": "12345", "amount": "5", "note": "x"}, "Belgi 8 sanly bolmaly"),
        ({"phone": OTHER_PHONE, "amount": "", "note": "x"}, "aralygynda san giriziň"),
        ({"phone": OTHER_PHONE, "amount": "0", "note": "x"}, "aralygynda san giriziň"),
        ({"phone": OTHER_PHONE, "amount": "2.5", "note": "x"}, "aralygynda san giriziň"),
        ({"phone": OTHER_PHONE, "amount": "1_000", "note": "x"}, "aralygynda san giriziň"),
        ({"phone": OTHER_PHONE, "amount": "٣", "note": "x"}, "aralygynda san giriziň"),
        ({"phone": OTHER_PHONE, "amount": "1001", "note": "x"}, "aralygynda san giriziň"),
        ({"phone": OTHER_PHONE, "amount": "5", "note": "  "}, "Näme üçin berilýändigini"),
        ({"phone": OTHER_PHONE, "amount": "5", "note": "x" * 501}, "500 harpdan uzyn"),
    ],
)
def test_bad_grants_are_refused_and_write_nothing(admin, db, form, field_error):
    user_id(db, OTHER_PHONE)
    response = admin.post("/admin/stars", data=form)
    assert response.status_code == 400
    assert field_error in response.text
    assert rows(db) == []


def test_admin_looks_up_a_reader_by_phone(admin, db):
    reader = user_id(db, OTHER_PHONE)
    stars.grant(db, reader, 7, "Bonus")
    page = admin.get("/admin/stars", params={"phone": "65 111222"}).text
    assert "Balansy: <strong>7 ýyldyz</strong>" in page
    unknown = admin.get("/admin/stars", params={"phone": "+99365999999"})
    assert unknown.status_code == 200 and "Bu belgi bilen hasap ýok" in unknown.text


def test_recent_entries_list_every_reader(admin, db):
    stars.grant(db, user_id(db, OTHER_PHONE), 3, "Birinji")
    stars.grant(db, user_id(db, "+99364000001"), 4, "Ikinji")
    page = admin.get("/admin/stars").text
    assert "+993 65 111222" in page and "+993 64 000001" in page
    assert page.index("Ikinji") < page.index("Birinji")  # newest first


def test_admin_has_a_stars_tab(admin):
    html = admin.get("/admin/stars").text
    tabs = re.search(r'<nav class="tab-bar".*?</nav>', html, flags=re.S).group(0)
    assert '<a href="/admin/stars" aria-current="page">' in tabs


# --- What the reader sees --------------------------------------------------------------------


def test_header_shows_the_balance_only_when_signed_in(client, db):
    assert 'class="star-balance"' not in client.get("/").text
    login(client)
    stars.grant(db, user_id(db), 4, "Bonus")
    assert header_balance(client.get("/").text) == 4
    assert header_balance(client.get("/books").text) == 4
    assert header_balance(client.get("/no-such-page").text) == 4


def test_history_requires_signing_in(client):
    response = client.get("/account/stars", follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"].startswith("/login")


def test_fresh_account_has_an_empty_history_and_a_zero_balance(client):
    login(client)
    html = client.get("/account/stars").text
    assert header_balance(html) == 0
    assert "Entek hiç hili ýazgy ýok" in html
    assert "<table" not in html


def test_header_balance_matches_a_history_of_a_dozen_entries(client, db):
    login(client)
    uid = user_id(db)
    stars.grant(db, uid, 20, "Başlangyç")
    for book in range(1, 9):
        append(db, uid, -1, "spend", f"book:{book}", f"Kitap {book}")
    append(db, uid, 1, "refund", "book:3", "Faýl bozuk")
    stars.grant(db, uid, -2, "Düzediş")
    append(db, uid, 0, "spend", "book:9", "Mugt kitap")
    append(db, uid, 5, "topup", "pay:1", None)
    assert len(rows(db, uid)) == 13

    html = client.get("/account/stars").text
    amounts = re.findall(r'class="num ledger-amount[^"]*">([^<]+)<', html)
    assert len(amounts) == 13
    total = sum(int(a.replace("−", "-").replace("+", "")) for a in amounts)
    after = [int(a) for a in re.findall(r'class="num ledger-after" data-label="Galan">(-?\d+)<', html)]
    assert total == stars.balance(db, uid) == header_balance(html) == after[0] == 16
    assert after[-1] == 20  # the oldest row is the first grant


def test_history_explains_each_entry(client, db):
    from tests.test_catalogue import add_book

    login(client)
    uid = user_id(db)
    book_id = add_book(db, "Görogly", price=3)
    stars.grant(db, uid, 10, "Synagçy bonusy")
    append(db, uid, -3, "spend", f"book:{book_id}", "Görogly")
    append(db, uid, 0, "spend", "book:999", "Pozulan kitap")

    html = client.get("/account/stars").text
    assert "Administrator berdi" in html and "Synagçy bonusy" in html
    assert "Kitap satyn alyndy" in html
    assert f'<a href="/books/{book_id}">Görogly</a>' in html
    # A book that is gone keeps its title, without a dead link.
    assert "<span>Pozulan kitap</span>" in html
    assert "−3" in html and "+10" in html


def test_history_shows_local_time(client, db):
    login(client)
    uid = user_id(db)
    stars.grant(db, uid, 1, "a")
    stored = rows(db, uid)[0]["created_at"]
    from app.templating import _localtime

    assert _localtime("2026-09-23 21:30:00") == "24.09.2026 02:30"  # UTC+5, past midnight
    assert _localtime(stored) in client.get("/account/stars").text


def test_account_page_shows_the_balance_and_links_to_the_history(client, db):
    login(client)
    stars.grant(db, user_id(db), 6, "a")
    html = client.get("/account").text
    assert '<a href="/account/stars">6 ýyldyz</a>' in html
    assert "ýakyn wagtda" not in html
