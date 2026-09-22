"""What a PDF knows about itself (Sprint 04 tasks 4 and 5).

Embedded metadata is frequently wrong — scanners write their own name as the author, and
titles are often a filename — so everything here is a suggestion for the admin, never an
authority.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

log = logging.getLogger(__name__)

# Covers load on mobile connections: 360px wide is enough for a two-column phone grid on a
# high-density screen, and keeps a cover around 20-40 KB.
COVER_WIDTH = 360
COVER_JPEG_QUALITY = 80
RENDER_TIMEOUT_SECONDS = 60


@dataclass(frozen=True)
class PdfInfo:
    page_count: int | None
    title: str | None
    author: str | None


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def read_info(path: Path) -> PdfInfo:
    """Page count and embedded title/author. Never raises: a PDF pypdf cannot read still gets
    stored, it just arrives without suggestions."""
    try:
        # An open file, never a path: given a path, PdfReader reads the whole file into a
        # BytesIO first — 150 MB of RAM for a 150 MB scan. From a file it seeks and reads only
        # the cross-reference table, page tree and info dictionary.
        with path.open("rb") as handle:
            reader = PdfReader(handle)
            page_count = len(reader.pages)
            meta = reader.metadata
            title = _clean(meta.title) if meta else None
            author = _clean(meta.author) if meta else None
    except Exception:  # pypdf raises a wide variety of errors on damaged files
        log.warning("Could not read PDF metadata from %s", path, exc_info=True)
        return PdfInfo(page_count=None, title=None, author=None)
    return PdfInfo(page_count=page_count, title=title, author=author)


def render_cover(pdf_path: Path, out_path: Path) -> bool:
    """Render the first page to a JPEG at out_path. Returns False if it could not be done.

    Uses poppler's pdftoppm in a subprocess rather than a Python PDF renderer: it runs outside
    the web process's memory, is one apt package on the server, and a crash on a malformed file
    takes down only itself.
    """
    pdftoppm = shutil.which("pdftoppm")
    if pdftoppm is None:
        log.warning("pdftoppm not installed; %s gets no rendered cover", pdf_path)
        return False
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # pdftoppm appends ".jpg" to the prefix it is given.
    prefix = out_path.with_suffix("")
    try:
        subprocess.run(
            [
                pdftoppm, "-f", "1", "-l", "1", "-singlefile",
                "-jpeg", "-jpegopt", f"quality={COVER_JPEG_QUALITY}",
                "-scale-to-x", str(COVER_WIDTH), "-scale-to-y", "-1",
                str(pdf_path), str(prefix),
            ],
            check=True,
            capture_output=True,
            timeout=RENDER_TIMEOUT_SECONDS,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        log.warning("pdftoppm failed on %s", pdf_path, exc_info=True)
        return False
    rendered = prefix.with_suffix(".jpg")
    if rendered != out_path:
        rendered.replace(out_path)
    return out_path.exists()
