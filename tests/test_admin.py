"""The admin panel over HTTP (Sprint 04)."""
from __future__ import annotations

import io
import re

import pytest
from PIL import Image

from app import storage
from tests.pdfs import make_pdf
from tests.test_auth import PHONE, login


@pytest.fixture()
def admin(client, db):
    login(client)
    db.execute("UPDATE users SET is_admin = 1 WHERE phone = ?", (PHONE,))
    db.commit()
    return client


def upload(client, data: bytes, filename="kitap.pdf", **fields):
    form = {"language": "tk", "price_stars": "0", **fields}
    return client.post(
        "/admin/books",
        data=form,
        files={"pdf": (filename, data, "application/pdf")},
        follow_redirects=False,
    )


def uploaded_id(response) -> int:
    assert response.status_code == 303, response.text[:500]
    return int(re.search(r"/admin/books/(\d+)", response.headers["location"]).group(1))


# --- The guard -------------------------------------------------------------------------------

ADMIN_REQUESTS = [
    ("get", "/admin"),
    ("get", "/admin/books"),
    ("get", "/admin/books/new"),
    ("get", "/admin/books/1"),
    ("get", "/admin/books/1/delete"),
    ("post", "/admin/books"),
    ("post", "/admin/books/1"),
    ("post", "/admin/books/1/publish"),
    ("post", "/admin/books/1/unpublish"),
    ("post", "/admin/books/1/cover"),
    ("post", "/admin/books/1/cover/render"),
    ("post", "/admin/books/1/delete"),
]


@pytest.mark.parametrize("method, path", ADMIN_REQUESTS)
def test_every_admin_endpoint_is_404_for_a_signed_out_visitor(client, method, path):
    response = getattr(client, method)(path, follow_redirects=False)
    assert response.status_code == 404


@pytest.mark.parametrize("method, path", ADMIN_REQUESTS)
def test_every_admin_endpoint_is_404_for_a_normal_reader(client, db, method, path):
    login(client)
    # A real book exists, so a 404 cannot be explained by "book 1 not found".
    storage.ingest(db, storage.stage(io.BytesIO(make_pdf())), original_filename="a.pdf")
    response = getattr(client, method)(path, follow_redirects=False)
    assert response.status_code == 404


def test_upload_by_a_normal_reader_is_refused_and_stores_nothing(client, db):
    login(client)
    response = upload(client, make_pdf())
    assert response.status_code == 404
    assert db.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 0


def test_admin_reaches_the_panel_from_the_header(admin):
    home = admin.get("/").text
    assert 'href="/admin"' in home
    assert admin.get("/admin").status_code == 200


def test_normal_reader_sees_no_admin_link(client):
    login(client)
    assert 'href="/admin"' not in client.get("/").text


def test_admin_pages_still_carry_the_dev_banner(admin):
    for path in ("/admin", "/admin/books", "/admin/books/new"):
        assert "Ösüş tertibi" in admin.get(path).text


# --- Upload ----------------------------------------------------------------------------------


def test_admin_uploads_a_pdf_and_sees_it_in_the_list(admin, db):
    book_id = uploaded_id(upload(admin, make_pdf(), title="Görogly", author="Halk döredijiligi"))

    edit = admin.get(f"/admin/books/{book_id}?notice=uploaded")
    assert "Görogly" in edit.text
    assert "Kitap ýüklendi" in edit.text
    listing = admin.get("/admin/books").text
    assert "Görogly" in listing
    assert "Garalama" in listing
    assert db.execute("SELECT is_published FROM books").fetchone()[0] == 0


def test_duplicate_upload_under_another_name_is_refused_naming_the_existing_book(admin, db):
    data = make_pdf()
    first = uploaded_id(upload(admin, data, filename="bir.pdf", title="Ilkinji nusga"))

    response = upload(admin, data, filename="iki.pdf", title="Başga at")
    assert response.status_code == 409
    assert "Ilkinji nusga" in response.text
    assert f'/admin/books/{first}"' in response.text
    assert db.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 1


def test_non_pdf_upload_is_refused(admin, db):
    response = upload(admin, b"just some text", filename="kitap.pdf")
    assert response.status_code == 400
    assert "PDF däl" in response.text
    assert db.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 0


def test_upload_without_a_file_is_refused(admin):
    response = admin.post("/admin/books", data={"title": "x"}, follow_redirects=False)
    assert response.status_code == 400
    assert "PDF faýly saýlaň" in response.text


def test_upload_keeps_typed_values_when_a_field_is_invalid(admin, db):
    response = upload(admin, make_pdf(), title="Saklanmaly at", year="ýyl")
    assert response.status_code == 400
    assert 'value="Saklanmaly at"' in response.text
    assert "Ýyl 1 bilen" in response.text
    assert db.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 0


def test_embedded_metadata_is_offered_as_a_suggestion(admin):
    book_id = uploaded_id(upload(admin, make_pdf(title="PDF-däki at"), title="Admin at"))
    assert "PDF-de: «PDF-däki at»" in admin.get(f"/admin/books/{book_id}").text


# --- Edit and publish ------------------------------------------------------------------------


def test_upload_unpublished_edit_then_publish(admin, db):
    book_id = uploaded_id(upload(admin, make_pdf()))
    visible = lambda: {r[0] for r in db.execute("SELECT id FROM published_books")}  # noqa: E731
    assert visible() == set()

    saved = admin.post(
        f"/admin/books/{book_id}",
        data={"title": "Täze at", "author": "Täze awtor", "year": "1990", "language": "ru",
              "description": "Gysga.", "price_stars": "5"},
        follow_redirects=False,
    )
    assert saved.status_code == 303
    row = db.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    assert (row["title"], row["author"], row["year"], row["language"], row["price_stars"]) == (
        "Täze at", "Täze awtor", 1990, "ru", 5,
    )
    assert visible() == set()

    admin.post(f"/admin/books/{book_id}/publish")
    assert visible() == {book_id}
    admin.post(f"/admin/books/{book_id}/unpublish")
    assert visible() == set()


@pytest.mark.parametrize(
    "field, value, message",
    [
        ("title", "", "Kitabyň adyny giriziň"),
        ("year", "3000", "Ýyl 1 bilen"),
        ("price_stars", "-1", "Baha 0 bilen 1000"),
        ("language", "xx", "dilleriň birini"),
    ],
)
def test_invalid_edits_are_refused_with_a_message(admin, db, field, value, message):
    book_id = uploaded_id(upload(admin, make_pdf(), title="Asyl at"))
    form = {"title": "Asyl at", "author": "", "year": "", "language": "tk", "description": "",
            "price_stars": "0", field: value}

    response = admin.post(f"/admin/books/{book_id}", data=form)
    assert response.status_code == 400
    assert message in response.text
    assert db.execute("SELECT title FROM books").fetchone()[0] == "Asyl at"


def test_list_search_and_status_filter(admin):
    uploaded_id(upload(admin, make_pdf(title="a"), title="Magtymguly goşgulary"))
    second = uploaded_id(upload(admin, make_pdf(title="b"), title="Görogly"))
    admin.post(f"/admin/books/{second}/publish")

    assert "Görogly" not in admin.get("/admin/books?q=Magtym").text
    assert "Magtymguly" in admin.get("/admin/books?q=Magtym").text
    published = admin.get("/admin/books?status=published").text
    assert "Görogly" in published and "Magtymguly" not in published
    assert "tapylmady" in admin.get("/admin/books?q=%25").text  # LIKE wildcards are escaped


def test_missing_book_is_404(admin):
    assert admin.get("/admin/books/999").status_code == 404


# --- Covers ----------------------------------------------------------------------------------


def test_uploaded_cover_is_served(admin, db):
    book_id = uploaded_id(upload(admin, make_pdf()))
    png = io.BytesIO()
    Image.new("RGB", (800, 1200), "navy").save(png, "PNG")

    response = admin.post(
        f"/admin/books/{book_id}/cover",
        files={"cover": ("c.png", png.getvalue(), "image/png")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    cover_path = db.execute("SELECT cover_path FROM books").fetchone()[0]
    served = admin.get(f"/{cover_path}")
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/jpeg"


def test_bad_cover_upload_is_refused(admin):
    book_id = uploaded_id(upload(admin, make_pdf()))
    response = admin.post(
        f"/admin/books/{book_id}/cover", files={"cover": ("c.png", b"nope", "image/png")}
    )
    assert response.status_code == 400
    assert "surat däl" in response.text


@pytest.mark.parametrize("path", ["/covers/../x.jpg", "/covers/ab/..%2F..%2Fsecret.jpg", "/covers/zz/abc.jpg"])
def test_cover_route_serves_nothing_outside_covers(client, path):
    assert client.get(path).status_code == 404


def test_book_without_a_cover_still_displays(admin, db, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    book_id = uploaded_id(upload(admin, make_pdf(), title="Daşlyksyz"))
    assert db.execute("SELECT cover_path FROM books").fetchone()[0] is None

    page = admin.get(f"/admin/books/{book_id}").text
    assert "cover-blank" in page
    assert "<img" not in page


# --- Delete ----------------------------------------------------------------------------------


def test_delete_asks_first_then_removes_row_and_file(admin, db):
    book_id = uploaded_id(upload(admin, make_pdf(), title="Pozuljak"))
    content_hash = db.execute("SELECT content_hash FROM books").fetchone()[0]
    pdf = storage.media_root() / storage.pdf_relpath(content_hash)
    assert pdf.exists()

    confirm = admin.get(f"/admin/books/{book_id}/delete")
    assert "Pozuljak" in confirm.text and "pozulsynmy" in confirm.text
    assert db.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 1  # asking deletes nothing

    response = admin.post(f"/admin/books/{book_id}/delete", follow_redirects=False)
    assert response.status_code == 303
    assert db.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 0
    assert not pdf.exists()
