"""The public catalogue and book pages (Sprint 05)."""
from __future__ import annotations

import io
import itertools
import re
import shutil

import pytest

from app import storage
from app.catalogue import PAGE_SIZE
from tests.pdfs import make_pdf
from tests.test_auth import PHONE, login

_unique = itertools.count()
REAL_WHICH = shutil.which


def add_book(db, title, author="", language="tk", published=True, year=None, price=0, description=""):
    data = make_pdf(title=f"{title} {next(_unique)}")  # distinct bytes for every book
    return storage.ingest(
        db,
        storage.stage(io.BytesIO(data)),
        original_filename="kitap.pdf",
        title=title,
        author=author,
        language=language,
        year=year,
        price_stars=price,
        description=description,
        is_published=published,
    )


def titles(html: str) -> list[str]:
    return re.findall(r'<span class="book-card-title">([^<]*)</span>', html)


def is_not_found_page(response) -> bool:
    return response.status_code == 404 and "Sahypa tapylmady" in response.text


@pytest.fixture(autouse=True)
def no_cover_rendering(monkeypatch):
    # Most of these tests do not care about covers; skipping pdftoppm keeps them fast.
    monkeypatch.setattr(shutil, "which", lambda name: None)


# --- Catalogue -------------------------------------------------------------------------------


def test_catalogue_lists_published_books_only(client, db):
    add_book(db, "Görogly")
    add_book(db, "Gizlin garalama", published=False)

    response = client.get("/books")
    assert response.status_code == 200
    assert titles(response.text) == ["Görogly"]
    assert "Gizlin garalama" not in response.text


def test_catalogue_is_open_to_signed_out_visitors(client, db):
    add_book(db, "Görogly")
    assert titles(client.get("/books").text) == ["Görogly"]


def test_catalogue_shows_author_year_and_price(client, db):
    add_book(db, "Görogly", "Halk döredijiligi", year=1990, price=3)
    add_book(db, "Mugt kitap")
    html = client.get("/books").text
    assert "Halk döredijiligi" in html and "1990" in html and "3 ýyldyz" in html
    assert "Mugt" in html


def test_newest_first_by_default_and_by_title_on_request(client, db):
    for title in ["Bäri", "Älem", "Çöl"]:
        add_book(db, title)
    assert titles(client.get("/books").text) == ["Çöl", "Älem", "Bäri"]
    # Title order ignores diacritics, so Ä files with A.
    assert titles(client.get("/books?sort=title").text) == ["Älem", "Bäri", "Çöl"]


def test_unknown_sort_and_language_fall_back_to_defaults(client, db):
    add_book(db, "Görogly")
    response = client.get("/books?sort=drop+table&lang=xx")
    assert response.status_code == 200
    assert titles(response.text) == ["Görogly"]


def test_language_filter_and_counts(client, db):
    add_book(db, "Görogly", language="tk")
    add_book(db, "Каштанка", language="ru")
    add_book(db, "Кавказский пленник", language="ru")

    html = client.get("/books?lang=ru").text
    assert sorted(titles(html)) == ["Кавказский пленник", "Каштанка"]
    assert re.search(r'href="/books\?lang=ru" aria-current="true">Rusça <span class="chip-count">2</span>', html)
    assert re.search(r'Türkmençe <span class="chip-count">1</span>', html)
    assert "Iňlisçe" not in html  # no English books, so no English filter


def test_filters_are_plain_links_that_keep_the_search(client, db):
    add_book(db, "Görogly", language="tk")
    add_book(db, "Görogly (rusça)", language="ru")
    html = client.get("/books?q=gorogly").text
    assert 'href="/books?q=gorogly&amp;lang=ru"' in html
    assert 'href="/books?q=gorogly&amp;sort=title"' in html


# --- Pagination ------------------------------------------------------------------------------


def test_pagination_boundaries(client, db):
    for i in range(PAGE_SIZE + 5):
        add_book(db, f"Kitap {i:02d}")

    first = client.get("/books").text
    assert len(titles(first)) == PAGE_SIZE
    assert 'href="/books?page=2" rel="next"' in first
    assert 'rel="prev"' not in first

    last = client.get("/books?page=2").text
    assert len(titles(last)) == 5
    assert 'href="/books" rel="prev"' in last
    assert 'rel="next"' not in last

    # Past the end shows the last page rather than an empty one.
    assert titles(client.get("/books?page=99").text) == titles(last)


@pytest.mark.parametrize("page", ["0", "-3", "abc", "1.5", "", "9" * 5000])
def test_nonsense_page_numbers_show_the_first_page(client, db, page):
    add_book(db, "Görogly")
    response = client.get("/books", params={"page": page})
    assert response.status_code == 200
    assert titles(response.text) == ["Görogly"]


def test_pagination_keeps_search_and_filters(client, db):
    for i in range(PAGE_SIZE + 1):
        add_book(db, f"Ertekiler {i:02d}", language="tk")
    html = client.get("/books?q=ertekiler&lang=tk").text
    assert 'href="/books?q=ertekiler&amp;lang=tk&amp;page=2" rel="next"' in html


# --- Empty states ----------------------------------------------------------------------------


def test_empty_catalogue_is_a_real_page(client):
    response = client.get("/books")
    assert response.status_code == 200
    assert "Katalog entek boş" in response.text
    assert 'class="filters"' not in response.text


def test_no_results_suggests_other_spellings_and_a_request(client, db):
    add_book(db, "Görogly")
    response = client.get("/books?q=Magtymguly")
    assert response.status_code == 200
    assert "«Magtymguly» boýunça kitap tapylmady" in response.text
    assert "Bu kitaby soraň" in response.text  # the bridge to Sprint 07
    assert 'href="/books"' in response.text
    assert 'class="filters"' not in response.text  # nothing to filter


def test_empty_language_is_a_real_page(client, db):
    add_book(db, "Görogly", language="tk")
    response = client.get("/books?lang=en")
    assert response.status_code == 200
    assert "Bu dilde entek kitap ýok" in response.text
    assert 'href="/books"' in response.text and 'class="filters"' in response.text  # can switch back


def test_search_text_is_escaped(client, db):
    add_book(db, "Görogly")
    html = client.get("/books", params={"q": "<script>alert(1)</script>"}).text
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


# --- Book page -------------------------------------------------------------------------------


def test_book_page_shows_the_metadata(client, db):
    book_id = add_book(
        db, "Görogly", "Halk döredijiligi", year=1990, price=3,
        description="Birinji setir.\nIkinji setir.",
    )
    response = client.get(f"/books/{book_id}")
    assert response.status_code == 200
    html = response.text
    for text in ["Görogly", "Halk döredijiligi", "1990", "Türkmençe", "3 ýyldyz", "Birinji setir."]:
        assert text in html
    assert "<title>Görogly, Halk döredijiligi: Kitaphana</title>" in html


def test_anonymous_visitor_is_invited_to_log_in_and_come_back(client, db):
    book_id = add_book(db, "Görogly")
    html = client.get(f"/books/{book_id}").text
    assert f'href="/login?next=%2Fbooks%2F{book_id}"' in html
    assert "Ýüklemek üçin giriň" in html


def test_signed_in_reader_sees_the_download_button_waiting_for_sprint_06(client, db):
    book_id = add_book(db, "Görogly", price=2)
    login(client)
    html = client.get(f"/books/{book_id}").text
    assert re.search(r"<button type=\"button\" disabled>Ýükle</button>", html)
    assert "indiki tapgyrda" in html
    assert "2 ýyldyz gerek bolar" in html
    assert "Ýüklemek üçin giriň" not in html


def test_book_without_a_cover_renders(client, db):
    book_id = add_book(db, "Daşlyksyz kitap")
    html = client.get(f"/books/{book_id}").text
    assert "cover-blank" in html
    assert "<img" not in html


def test_book_with_a_cover_sets_its_size(client, db, monkeypatch):
    # Render covers again for this one test. Only shutil.which is restored: monkeypatch.undo()
    # would also undo the test settings and write into the real media directory.
    monkeypatch.setattr(shutil, "which", REAL_WHICH)
    if REAL_WHICH("pdftoppm") is None:
        pytest.skip("poppler not installed")
    add_book(db, "Daşlykly kitap")
    add_book(db, "Ikinji")
    html = client.get("/books").text
    assert html.count('width="360" height="540"') == 2
    assert 'loading="lazy"' not in html  # the first few covers load straight away


def test_unpublished_book_is_404_even_by_direct_url(client, db):
    book_id = add_book(db, "Gizlin garalama", published=False)
    assert is_not_found_page(client.get(f"/books/{book_id}"))


def test_unpublished_book_is_404_for_an_admin_too(client, db):
    book_id = add_book(db, "Gizlin garalama", published=False)
    login(client)
    db.execute("UPDATE users SET is_admin = 1 WHERE phone = ?", (PHONE,))
    db.commit()
    assert is_not_found_page(client.get(f"/books/{book_id}"))


@pytest.mark.parametrize(
    "path",
    [
        "/books/999",
        "/books/abc",
        "/books/0",
        "/books/007",
        "/books/-1",
        "/books/1.0",
        "/books/9223372036854775808",  # one past SQLite's largest integer
        "/books/99999999999999999999999",
    ],
)
def test_unknown_or_malformed_book_urls_are_404(client, db, path):
    add_book(db, "Görogly")
    assert is_not_found_page(client.get(path))


def test_huge_admin_book_id_is_404_not_a_crash(client, db):
    login(client)
    db.execute("UPDATE users SET is_admin = 1 WHERE phone = ?", (PHONE,))
    db.commit()
    assert client.get("/admin/books/99999999999999999999").status_code == 404


# --- The 404 page ----------------------------------------------------------------------------


def test_unknown_url_gets_the_real_404_page(client):
    response = client.get("/no/such/page")
    assert is_not_found_page(response)
    assert 'action="/books"' in response.text  # offers a search


def test_404_page_knows_who_is_signed_in(client):
    login(client)
    html = client.get("/no/such/page").text
    assert 'href="/account"' in html
    assert 'href="/login"' not in html


def test_admin_404_looks_like_any_other_404(client):
    login(client)
    assert is_not_found_page(client.get("/admin"))
