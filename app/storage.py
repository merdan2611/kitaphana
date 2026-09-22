"""Book files on disk, named by content hash (Sprint 04, ADR-0002).

`stage` then `ingest` is the only way a PDF enters the library: the admin upload uses it, the
fixture seed script uses it, and Phase 3's bulk importer will use it. Files are streamed in
fixed-size chunks and hashed on the way through, so memory use does not depend on file size.

Layout under MEDIA_DIR:
    books/ab/cd/abcd…(64 hex).pdf    fanned out by the first four hex digits: 65,536 leaf
                                     directories, so 30,000 books average under one per folder
    covers/ab/abcd….jpg              one small JPEG per book, same hash
    tmp/                             uploads in flight; same filesystem, so moving is a rename
"""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from PIL import Image, UnidentifiedImageError

from app import config, pdfmeta
from app.db import timestamp
from app.search import book_search_text

CHUNK_SIZE = 1024 * 1024
# The PDF spec allows junk before the header as long as it starts within the first 1024 bytes.
HEADER_WINDOW = 1024
PDF_MAGIC = b"%PDF-"
_HASH = re.compile(r"[0-9a-f]{64}")
# ~25 megapixels: any real cover scan, decoded in well under 100 MB.
MAX_COVER_PIXELS = 25_000_000


class IngestError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotAPdf(IngestError):
    def __init__(self) -> None:
        super().__init__("Bu faýl PDF däl. Diňe PDF faýllar kabul edilýär.")


class TooLarge(IngestError):
    def __init__(self, limit_mb: int) -> None:
        super().__init__(f"Faýl gaty uly: iň köp {limit_mb} MB bolup biler.")


class Duplicate(IngestError):
    def __init__(self, existing: sqlite3.Row) -> None:
        super().__init__(f"Bu faýl kitaphanada eýýäm bar: «{existing['title']}».")
        self.existing = existing


class NotAnImage(IngestError):
    def __init__(self) -> None:
        super().__init__("Bu faýl surat däl. JPEG ýa-da PNG ýükläň.")


# --- Paths -----------------------------------------------------------------------------------


def media_root() -> Path:
    return config.settings.media_dir


def tmp_dir() -> Path:
    path = media_root() / "tmp"
    path.mkdir(parents=True, exist_ok=True)
    return path


def pdf_relpath(content_hash: str) -> str:
    _check_hash(content_hash)
    return f"books/{content_hash[:2]}/{content_hash[2:4]}/{content_hash}.pdf"


def cover_relpath(content_hash: str) -> str:
    _check_hash(content_hash)
    return f"covers/{content_hash[:2]}/{content_hash}.jpg"


def _check_hash(content_hash: str) -> None:
    # Paths are built from this string, so it must never be able to contain "/" or "..".
    if not _HASH.fullmatch(content_hash):
        raise ValueError(f"not a SHA-256 hex digest: {content_hash!r}")


# --- Staging ---------------------------------------------------------------------------------


@dataclass
class StagedFile:
    """An uploaded file on disk under tmp/, hashed, not yet in the library."""

    path: Path
    content_hash: str
    size: int

    def discard(self) -> None:
        self.path.unlink(missing_ok=True)


def stage(source: BinaryIO, max_bytes: int | None = None) -> StagedFile:
    """Copy `source` to tmp/ in CHUNK_SIZE pieces, hashing as it goes. Raises NotAPdf/TooLarge.

    Nothing larger than one chunk is ever held in memory, whatever the file's size.
    """
    if max_bytes is None:
        max_bytes = config.settings.max_upload_mb * 1024 * 1024
    digest = hashlib.sha256()
    size = 0
    fd, name = tempfile.mkstemp(dir=tmp_dir(), suffix=".part")
    path = Path(name)
    try:
        with os.fdopen(fd, "wb") as out:
            head = source.read(HEADER_WINDOW)
            if PDF_MAGIC not in head:
                raise NotAPdf()
            chunk = head
            while chunk:
                size += len(chunk)
                if size > max_bytes:
                    raise TooLarge(config.settings.max_upload_mb)
                digest.update(chunk)
                out.write(chunk)
                chunk = source.read(CHUNK_SIZE)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return StagedFile(path=path, content_hash=digest.hexdigest(), size=size)


# --- Ingest ----------------------------------------------------------------------------------


def find_by_hash(conn: sqlite3.Connection, content_hash: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT id, title, author FROM books WHERE content_hash = ?", (content_hash,)
    ).fetchone()


def ingest(
    conn: sqlite3.Connection,
    staged: StagedFile,
    *,
    original_filename: str,
    title: str = "",
    author: str = "",
    year: int | None = None,
    language: str = "tk",
    description: str = "",
    price_stars: int = 0,
    is_published: bool = False,
    is_fixture: bool = False,
) -> int:
    """Move a staged file into the library and create its book row. Returns the new book id.

    Raises Duplicate (after discarding the staged file) if these bytes are already a book.
    Blank title or author are filled from the PDF's embedded metadata, then the filename.
    """
    existing = find_by_hash(conn, staged.content_hash)
    if existing is not None:
        staged.discard()
        raise Duplicate(existing)

    info = pdfmeta.read_info(staged.path)
    title = title.strip() or info.title or Path(original_filename).stem or "Atsyz kitap"
    author = author.strip() or info.author or ""

    pdf_path = media_root() / pdf_relpath(staged.content_hash)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    os.replace(staged.path, pdf_path)

    cover = cover_relpath(staged.content_hash)
    has_cover = pdfmeta.render_cover(pdf_path, media_root() / cover)

    now = timestamp()
    try:
        cursor = conn.execute(
            "INSERT INTO books (title, author, year, language, description, content_hash,"
            " file_size, page_count, cover_path, price_stars, is_published, original_filename,"
            " is_fixture, created_at, updated_at, search_text)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                title, author, year, language, description.strip(), staged.content_hash,
                staged.size, info.page_count, cover if has_cover else None, price_stars,
                int(is_published), original_filename, int(is_fixture), now, now,
                book_search_text(title, author),
            ),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        # Lost a race with an identical upload. The file now on disk is byte-for-byte the other
        # book's file, so it stays where it is.
        conn.rollback()
        raise Duplicate(find_by_hash(conn, staged.content_hash))
    return cursor.lastrowid


def ingest_path(conn: sqlite3.Connection, path: Path, **fields) -> int:
    """Stage and ingest a file already on disk: the same path an upload takes."""
    with path.open("rb") as source:
        staged = stage(source)
    return ingest(conn, staged, original_filename=path.name, **fields)


# --- Covers and deletion ---------------------------------------------------------------------


def store_uploaded_cover(conn: sqlite3.Connection, book_id: int, source: BinaryIO) -> None:
    """Replace a book's cover with an uploaded image, resized like a rendered one."""
    book = conn.execute("SELECT content_hash FROM books WHERE id = ?", (book_id,)).fetchone()
    try:
        with Image.open(source) as image:
            # Checked from the header, before decoding: Pillow's own bomb limit would still let
            # a ~270 MB decode through, which a 2 GB server cannot spare.
            if image.width * image.height > MAX_COVER_PIXELS:
                raise NotAnImage()
            image.draft("RGB", (pdfmeta.COVER_WIDTH * 2, pdfmeta.COVER_WIDTH * 4))  # JPEG only
            image.load()
            image = image.convert("RGB")
            if image.width > pdfmeta.COVER_WIDTH:
                height = round(image.height * pdfmeta.COVER_WIDTH / image.width)
                image = image.resize((pdfmeta.COVER_WIDTH, height), Image.Resampling.LANCZOS)
            relpath = cover_relpath(book["content_hash"])
            out = media_root() / relpath
            out.parent.mkdir(parents=True, exist_ok=True)
            image.save(out, "JPEG", quality=pdfmeta.COVER_JPEG_QUALITY, optimize=True)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise NotAnImage() from exc
    conn.execute(
        "UPDATE books SET cover_path = ?, updated_at = ? WHERE id = ?",
        (relpath, timestamp(), book_id),
    )
    conn.commit()


def rerender_cover(conn: sqlite3.Connection, book_id: int) -> bool:
    """Replace a book's cover with its PDF's first page again."""
    book = conn.execute("SELECT content_hash FROM books WHERE id = ?", (book_id,)).fetchone()
    relpath = cover_relpath(book["content_hash"])
    ok = pdfmeta.render_cover(media_root() / pdf_relpath(book["content_hash"]), media_root() / relpath)
    conn.execute(
        "UPDATE books SET cover_path = ?, updated_at = ? WHERE id = ?",
        (relpath if ok else None, timestamp(), book_id),
    )
    conn.commit()
    return ok


def delete_book(conn: sqlite3.Connection, book_id: int) -> None:
    """Delete the row, then the file and cover — unless another row still points at them."""
    book = conn.execute("SELECT content_hash FROM books WHERE id = ?", (book_id,)).fetchone()
    if book is None:
        return
    content_hash = book["content_hash"]
    conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
    conn.commit()
    # content_hash is UNIQUE, so this should always be zero. Checked anyway: deleting a file
    # another book still serves would be unrecoverable, and a schema change could allow it.
    still_used = conn.execute(
        "SELECT COUNT(*) FROM books WHERE content_hash = ?", (content_hash,)
    ).fetchone()[0]
    if still_used:
        return
    (media_root() / pdf_relpath(content_hash)).unlink(missing_ok=True)
    (media_root() / cover_relpath(content_hash)).unlink(missing_ok=True)
