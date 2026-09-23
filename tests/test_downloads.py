"""Downloads (Sprint 06): stars are checked, the ledger is written, nginx (or, in development,
the app) sends the file. The most important tests in the project."""
from __future__ import annotations

import threading
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from app import sessions, stars, storage
from app.downloads import content_disposition, download_filename
from app.main import app
from tests.test_auth import PHONE, login
from tests.test_catalogue import add_book, no_cover_rendering  # noqa: F401 (autouse fixture)
from tests.test_stars import rows, user_id


@pytest.fixture()
def reader(client, db):
    """A signed-in reader; returns their user id."""
    login(client)
    return user_id(db)


def download(client, book_id):
    return client.post(f"/books/{book_id}/download", follow_redirects=False)


def fetch(client, book_id, **kwargs):
    return client.get(f"/books/{book_id}/file", follow_redirects=False, **kwargs)


def book_bytes(db, book_id) -> bytes:
    content_hash = db.execute("SELECT content_hash FROM books WHERE id = ?", (book_id,)).fetchone()[0]
    return (storage.media_root() / storage.pdf_relpath(content_hash)).read_bytes()


def spends(db, uid):
    return [(row["amount"], row["reference"]) for row in rows(db, uid) if row["reason"] == "spend"]


# --- Paying ----------------------------------------------------------------------------------


def test_a_priced_download_costs_exactly_the_price(client, db, reader):
    stars.grant(db, reader, 10, "Bonus")
    book_id = add_book(db, "Görogly", price=3)

    response = download(client, book_id)
    assert response.status_code == 303
    assert response.headers["location"] == f"/books/{book_id}/file"
    assert stars.balance(db, reader) == 7
    [row] = [r for r in rows(db, reader) if r["reason"] == "spend"]
    assert (row["amount"], row["reference"], row["note"]) == (-3, f"book:{book_id}", "Görogly")

    assert fetch(client, book_id).status_code == 200


def test_a_book_paid_for_once_downloads_again_for_free(client, db, reader):
    stars.grant(db, reader, 10, "Bonus")
    book_id = add_book(db, "Görogly", price=3)
    download(client, book_id)
    download(client, book_id)
    assert stars.balance(db, reader) == 7
    # The second download is still recorded.
    assert spends(db, reader) == [(-3, f"book:{book_id}"), (0, f"book:{book_id}")]
    page = client.get(f"/books/{book_id}").text
    assert "eýýäm satyn aldyňyz" in page


def test_after_a_refund_the_book_must_be_paid_for_again(client, db, reader):
    stars.grant(db, reader, 10, "Bonus")
    book_id = add_book(db, "Görogly", price=3)
    download(client, book_id)
    with stars.transaction(db):
        stars.append_entry(db, reader, 3, "refund", f"book:{book_id}", "Faýl bozuk")
    assert stars.balance(db, reader) == 10
    assert fetch(client, book_id).headers["location"] == f"/books/{book_id}"

    download(client, book_id)
    assert stars.balance(db, reader) == 7


def test_an_underfunded_download_explains_itself_and_writes_nothing(client, db, reader):
    stars.grant(db, reader, 2, "Bonus")
    book_id = add_book(db, "Görogly", price=5)

    response = download(client, book_id)
    assert response.status_code == 402
    html = response.text
    assert "Ýyldyz ýetmeýär" in html
    assert "5 ýyldyz" in html and "2 ýyldyz" in html and "3 ýyldyz" in html  # price, balance, missing
    assert "administrator" in html and "+993 61 234567" in html
    assert spends(db, reader) == []
    assert stars.balance(db, reader) == 2
    assert fetch(client, book_id).status_code == 303  # and no file either


def test_book_page_warns_before_an_underfunded_download(client, db, reader):
    book_id = add_book(db, "Görogly", price=5)
    html = client.get(f"/books/{book_id}").text
    assert "Balansyňyz 0 ýyldyz, bu kitap üçin 5 ýyldyz" in html


def test_book_page_says_what_will_be_left(client, db, reader):
    stars.grant(db, reader, 8, "Bonus")
    book_id = add_book(db, "Görogly", price=5)
    assert "soň 3 ýyldyz galar" in client.get(f"/books/{book_id}").text


# --- Free books ------------------------------------------------------------------------------


def test_a_free_book_downloads_with_no_stars_and_is_recorded(client, db, reader):
    book_id = add_book(db, "Mugt kitap", price=0)
    assert "Bu kitap mugt" in client.get(f"/books/{book_id}").text

    response = download(client, book_id)
    assert response.status_code == 303
    assert spends(db, reader) == [(0, f"book:{book_id}")]
    assert stars.balance(db, reader) == 0
    assert fetch(client, book_id).status_code == 200


def test_a_free_book_given_a_price_must_then_be_paid_for(client, db, reader):
    book_id = add_book(db, "Görogly", price=0)
    download(client, book_id)
    db.execute("UPDATE books SET price_stars = 4 WHERE id = ?", (book_id,))
    db.commit()
    assert fetch(client, book_id).headers["location"] == f"/books/{book_id}"
    assert download(client, book_id).status_code == 402


# --- Who may download ------------------------------------------------------------------------


def test_anonymous_visitors_are_sent_to_sign_in_and_nothing_is_written(client, db):
    book_id = add_book(db, "Görogly", price=0)
    for response in (download(client, book_id), fetch(client, book_id)):
        assert response.status_code == 303
        assert response.headers["location"] == f"/login?next=%2Fbooks%2F{book_id}"
    assert rows(db) == []


def test_unpublished_books_are_404_and_write_nothing(client, db, reader):
    stars.grant(db, reader, 10, "Bonus")
    book_id = add_book(db, "Garalama", price=1, published=False)
    assert download(client, book_id).status_code == 404
    assert fetch(client, book_id).status_code == 404
    assert spends(db, reader) == []


def test_unpublishing_stops_downloads_of_a_paid_book(client, db, reader):
    stars.grant(db, reader, 10, "Bonus")
    book_id = add_book(db, "Görogly", price=1)
    download(client, book_id)
    db.execute("UPDATE books SET is_published = 0 WHERE id = ?", (book_id,))
    db.commit()
    assert fetch(client, book_id).status_code == 404


@pytest.mark.parametrize("bad_id", ["0", "01", "-1", "abc", "1.0", "9" * 25])
def test_malformed_ids_are_404(client, reader, bad_id):
    assert download(client, bad_id).status_code == 404
    assert fetch(client, bad_id).status_code == 404


def test_the_file_url_alone_never_writes_or_charges(client, db, reader):
    stars.grant(db, reader, 10, "Bonus")
    book_id = add_book(db, "Görogly", price=3)
    response = fetch(client, book_id)
    assert response.status_code == 303 and response.headers["location"] == f"/books/{book_id}"
    assert stars.balance(db, reader) == 10 and spends(db, reader) == []


def test_download_must_be_a_post(client, db, reader):
    book_id = add_book(db, "Görogly", price=0)
    assert client.get(f"/books/{book_id}/download").status_code == 405
    assert spends(db, reader) == []


def test_a_missing_file_is_not_charged_for(client, db, reader):
    stars.grant(db, reader, 10, "Bonus")
    book_id = add_book(db, "Görogly", price=3)
    content_hash = db.execute("SELECT content_hash FROM books WHERE id = ?", (book_id,)).fetchone()[0]
    (storage.media_root() / storage.pdf_relpath(content_hash)).unlink()
    assert download(client, book_id).status_code == 404
    assert stars.balance(db, reader) == 10


def test_the_media_directory_is_not_reachable_by_url(client, db, reader):
    book_id = add_book(db, "Görogly", price=0)
    relpath = storage.pdf_relpath(
        db.execute("SELECT content_hash FROM books WHERE id = ?", (book_id,)).fetchone()[0]
    )
    for url in (f"/media/{relpath}", f"/{relpath}", f"/_protected/{relpath}", f"/static/../media/{relpath}"):
        assert client.get(url).status_code == 404, url


# --- Sending the file ------------------------------------------------------------------------


def test_nginx_mode_returns_an_empty_x_accel_redirect(client, db, reader, test_settings):
    test_settings(downloads_via_nginx=True)
    book_id = add_book(db, "Görogly", price=0)
    download(client, book_id)
    response = fetch(client, book_id)
    assert response.status_code == 200
    content_hash = db.execute("SELECT content_hash FROM books WHERE id = ?", (book_id,)).fetchone()[0]
    assert response.headers["x-accel-redirect"] == f"/_protected/books/{content_hash[:2]}/{content_hash[2:4]}/{content_hash}.pdf"
    assert response.content == b""
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("attachment;")
    assert response.headers["cache-control"] == "private"


def test_development_mode_streams_the_real_bytes(client, db, reader, test_settings):
    test_settings(downloads_via_nginx=False)
    book_id = add_book(db, "Görogly", price=0)
    download(client, book_id)
    response = fetch(client, book_id)
    assert response.status_code == 200
    assert "x-accel-redirect" not in response.headers
    assert response.content == book_bytes(db, book_id)
    assert response.content.startswith(b"%PDF-")
    assert response.headers["content-disposition"].startswith("attachment;")


def test_development_mode_resumes_a_partial_download(client, db, reader, test_settings):
    test_settings(downloads_via_nginx=False)
    book_id = add_book(db, "Görogly", price=0)
    download(client, book_id)
    whole = book_bytes(db, book_id)
    response = fetch(client, book_id, headers={"Range": "bytes=100-"})
    assert response.status_code == 206
    assert response.content == whole[100:]
    assert len(spends(db, reader)) == 1  # resuming is not another download


def test_following_the_redirect_downloads_the_file(client, db, reader, test_settings):
    test_settings(downloads_via_nginx=False)
    stars.grant(db, reader, 3, "Bonus")
    book_id = add_book(db, "Görogly", price=3)
    response = client.post(f"/books/{book_id}/download")  # follows the 303, as a browser does
    assert response.status_code == 200
    assert response.content == book_bytes(db, book_id)
    assert stars.balance(db, reader) == 0


# --- File names ------------------------------------------------------------------------------


def test_turkmen_titles_get_a_readable_encoded_filename(client, db, reader):
    book_id = add_book(db, "Älem we Ýaşaýyş", price=0)
    download(client, book_id)
    header = fetch(client, book_id).headers["content-disposition"]
    assert header == (
        "attachment; filename=\"Alem we Yasayys.pdf\"; "
        f"filename*=UTF-8''{quote('Älem we Ýaşaýyş.pdf', safe='')}"
    )
    # Standard percent-encoded UTF-8, as browsers decode it.
    assert "filename*=UTF-8''%C3%84lem%20we%20%C3%9Da%C5%9Fa%C3%BDy%C5%9F.pdf" in header


def test_a_title_with_no_latin_letters_falls_back_to_the_book_id():
    header = content_disposition(download_filename("Каштанка", 12), 12)
    assert 'filename="kitap-12.pdf"' in header
    assert f"filename*=UTF-8''{quote('Каштанка.pdf', safe='')}" in header


@pytest.mark.parametrize(
    "title, expected",
    [
        ('Kitap: "saýlanan" / eserler', "Kitap saýlanan eserler.pdf"),
        ("Iki\nsetir\tatly", "Iki setir atly.pdf"),
        ("Kitap‮FDP.exe", "KitapFDP.exe.pdf"),  # a right-to-left override is dropped
        ("Görogly.pdf", "Görogly.pdf"),
        ("...", "kitap-5.pdf"),
        ("", "kitap-5.pdf"),
        ("A" * 400, "A" * 150 + ".pdf"),
    ],
)
def test_filenames_are_cleaned(title, expected):
    assert download_filename(title, 5) == expected


def test_the_header_never_carries_quotes_or_line_breaks():
    header = content_disposition(download_filename('a"b\r\nc\\d', 1), 1)
    assert "\r" not in header and "\n" not in header
    assert header.count('"') == 2
    header.encode("latin-1")  # a header value must be latin-1 encodable


# --- Rate limits -----------------------------------------------------------------------------


def test_the_download_rate_limit_applies_to_free_books_too(client, db, reader, test_settings):
    test_settings(download_limits=((2, 3600), (30, 86400)))
    first, second, third = (add_book(db, f"Kitap {i}", price=0) for i in range(3))
    assert download(client, first).status_code == 303
    assert download(client, second).status_code == 303

    response = download(client, third)
    assert response.status_code == 429
    assert "gaty köp kitap ýüklediňiz" in response.text
    assert "minutdan soň" in response.text
    assert len(spends(db, reader)) == 2
    # Files already recorded can still be fetched (resuming is not a new download).
    assert fetch(client, first).status_code == 200


def test_a_rate_limited_priced_download_charges_nothing(client, db, reader, test_settings):
    test_settings(download_limits=((1, 3600),))
    stars.grant(db, reader, 10, "Bonus")
    download(client, add_book(db, "Birinji", price=0))
    assert download(client, add_book(db, "Ikinji", price=3)).status_code == 429
    assert stars.balance(db, reader) == 10


def test_the_daily_limit_says_hours(client, db, reader, test_settings):
    test_settings(download_limits=((10, 3600), (1, 86400)))
    download(client, add_book(db, "Birinji", price=0))
    response = download(client, add_book(db, "Ikinji", price=0))
    assert response.status_code == 429 and "sagatdan soň" in response.text


def test_limits_are_per_reader(client, db, reader, test_settings):
    test_settings(download_limits=((1, 3600),))
    book_id = add_book(db, "Kitap", price=0)
    download(client, book_id)
    other = TestClient(app, base_url="https://testserver")
    login(other, "+99365111222")
    assert download(other, book_id).status_code == 303


# --- Concurrency -----------------------------------------------------------------------------


def _simultaneous_downloads(client, book_ids):
    """POST each download from its own thread and client, all released at the same moment."""
    cookie = client.cookies.get(sessions.COOKIE_NAME)
    barrier = threading.Barrier(len(book_ids))
    statuses: list[int] = []

    def run(book_id):
        own = TestClient(app, base_url="https://testserver", cookies={sessions.COOKIE_NAME: cookie})
        barrier.wait()
        statuses.append(download(own, book_id).status_code)

    threads = [threading.Thread(target=run, args=(book_id,)) for book_id in book_ids]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return sorted(statuses)


def test_simultaneous_downloads_cannot_overdraw(client, db, reader):
    stars.grant(db, reader, 3, "Bonus")
    first, second = add_book(db, "Birinji", price=3), add_book(db, "Ikinji", price=3)
    assert _simultaneous_downloads(client, [first, second]) == [303, 402]
    assert stars.balance(db, reader) == 0
    assert len([amount for amount, _ in spends(db, reader) if amount < 0]) == 1


def test_simultaneous_downloads_of_one_book_charge_once(client, db, reader):
    stars.grant(db, reader, 10, "Bonus")
    book_id = add_book(db, "Görogly", price=3)
    assert _simultaneous_downloads(client, [book_id] * 3) == [303, 303, 303]
    assert stars.balance(db, reader) == 7
    assert sorted(amount for amount, _ in spends(db, reader)) == [-3, 0, 0]
