"""Storage, hashing, de-duplication, covers and the fixture seed (Sprint 04)."""
from __future__ import annotations

import hashlib
import io
import shutil

import pytest
from PIL import Image

from app import storage
from app.db import apply_migrations, connect
from scripts import seed_fixtures
from tests.pdfs import make_pdf

needs_pdftoppm = pytest.mark.skipif(shutil.which("pdftoppm") is None, reason="poppler not installed")


@pytest.fixture()
def conn(db_path):
    conn = connect(db_path)
    apply_migrations(conn)
    try:
        yield conn
    finally:
        conn.close()


def stage_bytes(data: bytes, **kwargs) -> storage.StagedFile:
    return storage.stage(io.BytesIO(data), **kwargs)


def tmp_files():
    return list(storage.tmp_dir().iterdir())


# --- Hashing and paths -----------------------------------------------------------------------


def test_hashing_a_known_file_produces_the_expected_sha256():
    data = b"%PDF-1.4\n" + b"kitaphana" * 500_000  # several chunks
    staged = stage_bytes(data)

    assert staged.content_hash == hashlib.sha256(data).hexdigest()
    assert staged.size == len(data)
    assert staged.path.read_bytes() == data


def test_known_file_matches_an_independently_computed_sha256():
    # Reference value from coreutils: printf '%PDF-1.4\nkitaphana\n' | sha256sum
    staged = stage_bytes(b"%PDF-1.4\nkitaphana\n")
    assert staged.content_hash == "2eb8d3779783f7b59b06865ef1401d6196da3e0e4b526cf4623e4f6e8017d0fd"


def test_hash_to_path_is_stable_and_fans_out():
    h = "ab" + "cd" + "e" * 60
    assert storage.pdf_relpath(h) == f"books/ab/cd/{h}.pdf"
    assert storage.pdf_relpath(h) == storage.pdf_relpath(h)
    assert storage.cover_relpath(h) == f"covers/ab/{h}.jpg"

    other = "ab" + "ef" + "e" * 60
    assert storage.pdf_relpath(other).rsplit("/", 1)[0] != storage.pdf_relpath(h).rsplit("/", 1)[0]


@pytest.mark.parametrize("bad", ["../../etc/passwd", "AB" + "c" * 62, "abc", "g" * 64, ""])
def test_paths_refuse_anything_but_a_hex_digest(bad):
    with pytest.raises(ValueError):
        storage.pdf_relpath(bad)


def test_stage_never_reads_more_than_one_chunk_at_a_time():
    class Recorder(io.BytesIO):
        largest = 0

        def read(self, size=-1):
            assert size != -1, "must never read the whole stream at once"
            Recorder.largest = max(Recorder.largest, size)
            return super().read(size)

    storage.stage(Recorder(b"%PDF-" + b"x" * (5 * storage.CHUNK_SIZE)))
    assert Recorder.largest <= storage.CHUNK_SIZE


# --- Rejections ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "data",
    [b"", b"Hello, this is a text file", b"\x89PNG\r\n\x1a\n" + b"\0" * 100, b"%PD"],
)
def test_a_file_that_is_not_a_pdf_is_rejected_and_nothing_is_left_behind(data):
    with pytest.raises(storage.NotAPdf):
        stage_bytes(data)
    assert tmp_files() == []


def test_header_after_leading_junk_is_accepted():
    staged = stage_bytes(b"\xef\xbb\xbf" + make_pdf())
    assert staged.size > 0


def test_a_file_over_the_limit_is_rejected_and_nothing_is_left_behind():
    with pytest.raises(storage.TooLarge):
        stage_bytes(b"%PDF-" + b"x" * 3000, max_bytes=2000)
    assert tmp_files() == []


# --- Ingest ----------------------------------------------------------------------------------


def test_ingest_stores_the_file_at_its_hash_path(conn):
    data = make_pdf(pages=3)
    book_id = storage.ingest(conn, stage_bytes(data), original_filename="kitap.pdf", title="Kitap")

    book = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    expected_hash = hashlib.sha256(data).hexdigest()
    assert book["content_hash"] == expected_hash
    stored = storage.media_root() / storage.pdf_relpath(expected_hash)
    assert stored.read_bytes() == data
    assert book["file_size"] == len(data)
    assert book["page_count"] == 3
    assert book["original_filename"] == "kitap.pdf"
    assert book["is_published"] == 0
    assert tmp_files() == []


def test_embedded_metadata_fills_blank_fields_only(conn):
    first = storage.ingest(
        conn, stage_bytes(make_pdf(title="Içki at", author="Içki awtor")), original_filename="a.pdf"
    )
    second = storage.ingest(
        conn,
        stage_bytes(make_pdf(title="Içki at 2", author="Içki awtor 2")),
        original_filename="b.pdf",
        title="Admin ýazan at",
    )
    rows = {r["id"]: r for r in conn.execute("SELECT id, title, author FROM books")}
    assert (rows[first]["title"], rows[first]["author"]) == ("Içki at", "Içki awtor")
    assert (rows[second]["title"], rows[second]["author"]) == ("Admin ýazan at", "Içki awtor 2")


def test_filename_is_the_last_resort_title(conn):
    book_id = storage.ingest(
        conn, stage_bytes(make_pdf(title=None, author=None)), original_filename="Gorkut ata.pdf"
    )
    row = conn.execute("SELECT title, author FROM books WHERE id = ?", (book_id,)).fetchone()
    assert (row["title"], row["author"]) == ("Gorkut ata", "")


def test_second_upload_of_the_same_bytes_is_a_duplicate_naming_the_first(conn):
    data = make_pdf()
    first = storage.ingest(conn, stage_bytes(data), original_filename="one.pdf", title="Birinji")

    staged = stage_bytes(data)
    with pytest.raises(storage.Duplicate) as excinfo:
        storage.ingest(conn, staged, original_filename="renamed.pdf", title="Başga at")

    assert excinfo.value.existing["id"] == first
    assert "Birinji" in excinfo.value.message
    assert not staged.path.exists()
    assert conn.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 1


@needs_pdftoppm
def test_first_page_is_rendered_as_a_small_cover(conn):
    book_id = storage.ingest(conn, stage_bytes(make_pdf()), original_filename="a.pdf")
    book = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()

    assert book["cover_path"] == storage.cover_relpath(book["content_hash"])
    with Image.open(storage.media_root() / book["cover_path"]) as image:
        assert image.format == "JPEG"
        assert image.width == 360


def test_book_without_a_renderer_gets_no_cover(conn, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    book_id = storage.ingest(conn, stage_bytes(make_pdf()), original_filename="a.pdf")
    assert conn.execute("SELECT cover_path FROM books WHERE id = ?", (book_id,)).fetchone()[0] is None


def test_uploaded_cover_is_resized_to_a_jpeg(conn):
    book_id = storage.ingest(conn, stage_bytes(make_pdf()), original_filename="a.pdf")
    png = io.BytesIO()
    Image.new("RGB", (1200, 1800), "red").save(png, "PNG")
    png.seek(0)

    storage.store_uploaded_cover(conn, book_id, png)

    path = conn.execute("SELECT cover_path FROM books WHERE id = ?", (book_id,)).fetchone()[0]
    with Image.open(storage.media_root() / path) as image:
        assert (image.format, image.size) == ("JPEG", (360, 540))


def test_uploaded_cover_that_is_not_an_image_is_rejected(conn):
    book_id = storage.ingest(conn, stage_bytes(make_pdf()), original_filename="a.pdf")
    with pytest.raises(storage.NotAnImage):
        storage.store_uploaded_cover(conn, book_id, io.BytesIO(b"not an image"))


def test_deleting_removes_the_row_the_file_and_the_cover(conn):
    book_id = storage.ingest(conn, stage_bytes(make_pdf()), original_filename="a.pdf")
    content_hash = conn.execute("SELECT content_hash FROM books").fetchone()[0]
    pdf = storage.media_root() / storage.pdf_relpath(content_hash)
    cover = storage.media_root() / storage.cover_relpath(content_hash)
    cover.parent.mkdir(parents=True, exist_ok=True)
    cover.write_bytes(b"jpeg")

    storage.delete_book(conn, book_id)

    assert conn.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 0
    assert not pdf.exists()
    assert not cover.exists()


def test_deleting_keeps_a_file_another_row_still_references(conn):
    # content_hash is UNIQUE, so two rows cannot share a file today; the guard is for a future
    # schema that allows it. Simulate that by making the "still used?" count report one row.
    book_id = storage.ingest(conn, stage_bytes(make_pdf()), original_filename="a.pdf")
    content_hash = conn.execute("SELECT content_hash FROM books").fetchone()[0]

    class SharedFileConnection:
        def execute(self, sql, params=()):
            if sql.startswith("SELECT COUNT(*) FROM books WHERE content_hash"):
                return conn.execute("SELECT 1")
            return conn.execute(sql, params)

        def commit(self):
            conn.commit()

    storage.delete_book(SharedFileConnection(), book_id)

    assert conn.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 0
    assert (storage.media_root() / storage.pdf_relpath(content_hash)).exists()


# --- Public visibility -----------------------------------------------------------------------


def test_unpublished_books_are_absent_from_the_public_view(conn):
    draft = storage.ingest(conn, stage_bytes(make_pdf(title="Garalama")), original_filename="a.pdf")
    live = storage.ingest(
        conn, stage_bytes(make_pdf(title="Neşir")), original_filename="b.pdf", is_published=True
    )
    visible = {r["id"] for r in conn.execute("SELECT id FROM published_books")}
    assert visible == {live}

    conn.execute("UPDATE books SET is_published = 1 WHERE id = ?", (draft,))
    assert {r["id"] for r in conn.execute("SELECT id FROM published_books")} == {draft, live}


# --- Fixture seed ----------------------------------------------------------------------------


def test_the_committed_manifest_is_complete():
    entries = seed_fixtures.load_manifest(seed_fixtures.MANIFEST)
    assert entries, "fixtures/books/manifest.yaml should list the placeholder books"
    for entry in entries:
        path = seed_fixtures.MANIFEST.parent / entry["filename"]
        assert path.is_file(), f"{entry['filename']} is listed but missing"
        assert path.read_bytes()[:5] == b"%PDF-"


def test_seed_loads_every_fixture_through_ingest_then_is_a_noop(conn):
    first = seed_fixtures.seed(conn)
    entries = seed_fixtures.load_manifest(seed_fixtures.MANIFEST)
    assert len(first.added) == len(entries) and first.skipped == []

    rows = conn.execute("SELECT * FROM books ORDER BY id").fetchall()
    for entry, row in zip(entries, rows):
        data = (seed_fixtures.MANIFEST.parent / entry["filename"]).read_bytes()
        assert row["content_hash"] == hashlib.sha256(data).hexdigest()
        assert row["is_fixture"] == 1
        assert row["title"] == entry["title"]
        assert (storage.media_root() / storage.pdf_relpath(row["content_hash"])).is_file()

    second = seed_fixtures.seed(conn)
    assert second.added == [] and len(second.skipped) == len(entries)
    assert conn.execute("SELECT COUNT(*) FROM books").fetchone()[0] == len(entries)


def test_seed_refuses_a_database_with_a_real_book(conn):
    storage.ingest(conn, stage_bytes(make_pdf()), original_filename="real.pdf")

    with pytest.raises(seed_fixtures.RefuseToSeed, match="real"):
        seed_fixtures.seed(conn)
    assert conn.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 1


def test_seed_refuses_an_entry_without_provenance(conn, tmp_path):
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text('- filename: a.pdf\n  title: "A"\n  language: "tk"\n')
    with pytest.raises(seed_fixtures.RefuseToSeed, match="source"):
        seed_fixtures.seed(conn, manifest)


def test_pdf_metadata_is_read_from_a_file_handle_not_a_path(monkeypatch, tmp_path):
    # Given a path, pypdf reads the whole file into memory first; a 150 MB scan would cost
    # 150 MB of RAM. This pins pdfmeta to passing an open file, which pypdf reads lazily.
    from app import pdfmeta

    received = []
    real_reader = pdfmeta.PdfReader

    def spy(stream, *args, **kwargs):
        received.append(stream)
        return real_reader(stream, *args, **kwargs)

    monkeypatch.setattr(pdfmeta, "PdfReader", spy)
    path = tmp_path / "a.pdf"
    path.write_bytes(make_pdf(pages=4))

    assert pdfmeta.read_info(path).page_count == 4
    assert hasattr(received[0], "read") and not isinstance(received[0], (str, type(path)))
