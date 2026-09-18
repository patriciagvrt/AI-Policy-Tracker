"""PDF text extraction using PyMuPDF (imported as `fitz`).

Kept intentionally simple: PyMuPDF's page.get_text() already does a
reasonable job of reading order for the kind of single-column policy PDFs
this project targets (e.g. Lund University's policy document). No OCR is
implemented, since the pilot's PDF source is a native-text PDF, not a
scanned image; the docstring says so explicitly rather than silently
returning an empty string for a scanned PDF.
"""

from __future__ import annotations

import pymupdf as fitz  # PyMuPDF (module renamed from `fitz`; alias kept for readability)


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """Extract text from a PDF's raw bytes.

    Returns:
        The concatenated text of every page, separated by blank lines.
        Returns an empty string if the PDF has no extractable text layer
        (e.g. a scanned image with no OCR) -- callers should check for
        this and record it as a collection error rather than silently
        storing an empty document.
    """
    text_parts: list[str] = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            page_text = page.get_text("text")
            if page_text.strip():
                text_parts.append(page_text.strip())
    return "\n\n".join(text_parts)


def extract_pdf_metadata(pdf_bytes: bytes) -> dict:
    """Return whatever title/creation-date metadata the PDF itself carries.

    PDF metadata is often incomplete or stale (e.g. "creation date" may be
    when a template was made, not when the policy was approved), so this is
    used as a fallback/cross-check, never as the sole source of
    publication_date.
    """
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        meta = dict(doc.metadata or {})
        meta["page_count"] = doc.page_count
    return meta
