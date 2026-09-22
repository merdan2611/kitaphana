"""Tiny, real PDFs for tests, built with pypdf so no binary fixtures are needed."""
from __future__ import annotations

import io

from pypdf import PdfWriter


def make_pdf(title: str | None = "Test kitaby", author: str | None = "Synag Awtory", pages: int = 2) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=420, height=595)
    metadata = {}
    if title:
        metadata["/Title"] = title
    if author:
        metadata["/Author"] = author
    if metadata:
        writer.add_metadata(metadata)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
