"""Search folding and matching (Sprint 05 task 2): the Turkmen letter problem."""
from __future__ import annotations

import io
import itertools
import re
import shutil

import pytest

from app import db as db_module
from app import search, storage
from app.db import apply_migrations, connect
from tests.pdfs import make_pdf

_unique = itertools.count()


def add_book(db, title, author="", language="tk", published=True):
    data = make_pdf(title=f"{title} {next(_unique)}")  # distinct bytes for every book
    return storage.ingest(
        db,
        storage.stage(io.BytesIO(data)),
        original_filename="kitap.pdf",
        title=title,
        author=author,
        language=language,
        is_published=published,
    )


def found_titles(client, query) -> list[str]:
    html = client.get("/books", params={"q": query}).text
    return re.findall(r'<span class="book-card-title">([^<]*)</span>', html)


@pytest.fixture(autouse=True)
def no_cover_rendering(monkeypatch):
    # Covers are irrelevant to search; skipping pdftoppm keeps these tests fast.
    monkeypatch.setattr(shutil, "which", lambda name: None)


# --- The folding function --------------------------------------------------------------------


@pytest.mark.parametrize(
    "text, folded",
    [
        ("alem", "alem"),
        ("älem", "alem"),
        ("ÄLEM", "alem"),
        ("Älem", "alem"),
        ("Ňň Şş Ýý Žž Öö Üü Çç Ää", "nn ss yy zz oo uu cc aa"),
        ("Каштанка", "каштанка"),
        ("КАШТАНКА", "каштанка"),
        ("Ёлка и йогурт", "елка и иогурт"),
        ("Baglar, heý!", "baglar hey"),
        ("  Görogly —  türkmen   halk eposy  ", "gorogly turkmen halk eposy"),
        ("O'Brien", "o brien"),
        ("", ""),
        (None, ""),
    ],
)
def test_fold(text, folded):
    assert search.fold(text) == folded


def test_query_terms_are_folded_words():
    assert search.query_terms("  Magtymguly   BAGLAR, heý! ") == ["magtymguly", "baglar", "hey"]


def test_query_terms_are_capped():
    assert len(search.query_terms(" ".join(["söz"] * 50))) == search.MAX_TERMS
    assert search.query_terms("a" * 500) == ["a" * search.MAX_QUERY_LENGTH]


@pytest.mark.parametrize("term, pattern", [("alem", "%alem%"), ("a_b", "%a\\_b%"), ("50%", "%50\\%%")])
def test_like_pattern_escapes_wildcards(term, pattern):
    assert search.like_pattern(term) == pattern


@pytest.mark.parametrize(
    "title, author",
    [("Älem we Adam", "Şaýyr"), ("Каштанка", "Антон Чехов"), ("Baglar, heý!", ""), ("x", "ÝÝ ňň")],
)
def test_app_and_sql_fold_agree(db_path, title, author):
    """Migration 004 fills old rows with SQL; the app fills new rows in Python. Same result."""
    conn = connect(db_path)
    try:
        sql = conn.execute("SELECT kitaphana_fold(? || ' ' || ?)", (title, author)).fetchone()[0]
    finally:
        conn.close()
    assert sql == search.book_search_text(title, author)


# --- Stored search text ----------------------------------------------------------------------


def test_ingest_stores_the_folded_text(db, client):
    book_id = add_book(db, "Älem we Adam", "Şaýyr Ýazyjy")
    stored = db.execute("SELECT search_text FROM books WHERE id = ?", (book_id,)).fetchone()[0]
    assert stored == "alem we adam sayyr yazyjy"


def test_migration_backfills_books_that_existed_before_it(tmp_path, monkeypatch):
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    for path in sorted(db_module.MIGRATIONS_DIR.glob("*.sql")):
        if path.name < "004":
            shutil.copy(path, migrations / path.name)
    monkeypatch.setattr(db_module, "MIGRATIONS_DIR", migrations)

    conn = connect(tmp_path / "old.db")
    try:
        apply_migrations(conn)
        conn.execute(
            "INSERT INTO books (title, author, language, content_hash, file_size, is_published)"
            " VALUES ('ÄLEM we Adam', 'Şaýyr', 'tk', 'hash', 1, 1)"
        )
        conn.commit()
        shutil.copy(
            db_module.BASE_DIR / "migrations" / "004-search-columns.sql",
            migrations / "004-search-columns.sql",
        )
        assert apply_migrations(conn) == ["004-search-columns.sql"]
        assert conn.execute("SELECT search_text FROM books").fetchone()[0] == "alem we adam sayyr"
        # The published_books view (SELECT *) picks up the new column too.
        assert conn.execute("SELECT search_text FROM published_books").fetchone()[0]
    finally:
        conn.close()


# --- Searching -------------------------------------------------------------------------------


@pytest.mark.parametrize("query", ["alem", "älem", "ÄLEM", "Alem", "ÄLem"])
def test_alem_alem_and_ALEM_find_the_same_book(client, db, query):
    add_book(db, "Älem we Adam")
    add_book(db, "Başga kitap")
    assert found_titles(client, query) == ["Älem we Adam"]


@pytest.mark.parametrize("query", ["каштанка", "КАШТАНКА", "Каштанка"])
def test_cyrillic_search_ignores_case(client, db, query):
    add_book(db, "Каштанка", "Антон Чехов", language="ru")
    assert found_titles(client, query) == ["Каштанка"]


def test_every_turkmen_letter_matches_without_its_mark(client, db):
    add_book(db, "Ňaňa Şaşa Ýaýa Žaža Öýe Üzüm Çeçe")
    for query in ["nana", "sasa", "yaya", "zaza", "oye", "uzum", "cece", "ŇAŇA", "ÜZÜM"]:
        assert found_titles(client, query) == ["Ňaňa Şaşa Ýaýa Žaža Öýe Üzüm Çeçe"], query


def test_search_matches_the_author_too(client, db):
    add_book(db, "Baglar, heý!", "Magtymguly Pyragy")
    add_book(db, "Görogly", "Halk döredijiligi")
    assert found_titles(client, "magtymguly") == ["Baglar, heý!"]
    assert found_titles(client, "PYRAGY") == ["Baglar, heý!"]


def test_every_word_must_match_but_across_title_and_author(client, db):
    add_book(db, "Baglar, heý!", "Magtymguly Pyragy")
    add_book(db, "Baglar", "Başga awtor")
    assert found_titles(client, "magtymguly baglar") == ["Baglar, heý!"]
    assert found_titles(client, "magtymguly görogly") == []


def test_part_of_a_word_is_enough(client, db):
    add_book(db, "Türkmen halk ertekileri")
    assert found_titles(client, "ertek") == ["Türkmen halk ertekileri"]


@pytest.mark.parametrize("query", ["%", "_", "%%", "!!!", "—"])
def test_wildcards_and_punctuation_match_nothing(client, db, query):
    add_book(db, "Görogly")
    add_book(db, "Älem")
    assert found_titles(client, query) == []


def test_search_never_shows_unpublished_books(client, db):
    add_book(db, "Älem we Adam", published=False)
    assert found_titles(client, "alem") == []


def test_search_text_follows_an_admin_edit(client, db):
    from tests.test_auth import PHONE, login

    book_id = add_book(db, "Köne at")
    login(client)
    db.execute("UPDATE users SET is_admin = 1 WHERE phone = ?", (PHONE,))
    db.commit()
    client.post(
        f"/admin/books/{book_id}",
        data={"title": "Täze Ýol", "author": "", "year": "", "language": "tk",
              "description": "", "price_stars": "0"},
    )
    assert found_titles(client, "taze yol") == ["Täze Ýol"]
    assert found_titles(client, "kone") == []
