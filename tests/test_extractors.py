"""Tests for HTML and PDF extraction (no live network -- local fixtures only)."""

from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF, only used here to *build* a throwaway test PDF

from nordic_ai_policy_tracker.collection.html_extractor import extract_main_text, extract_title
from nordic_ai_policy_tracker.collection.pdf_extractor import (
    extract_pdf_metadata,
    extract_text_from_pdf_bytes,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_extract_main_text_removes_boilerplate():
    html = (FIXTURES_DIR / "sample_policy.html").read_text(encoding="utf-8")
    text = extract_main_text(html)
    assert "Skip to content" not in text
    assert "All rights reserved" not in text
    assert "We use cookies" not in text
    assert "Home | Studies | Staff | Search" not in text


def test_extract_main_text_keeps_policy_content():
    html = (FIXTURES_DIR / "sample_policy.html").read_text(encoding="utf-8")
    text = extract_main_text(html)
    assert "generative AI tools to support their learning" in text
    assert "academic misconduct" in text


def test_extract_title_prefers_h1():
    html = (FIXTURES_DIR / "sample_policy.html").read_text(encoding="utf-8")
    assert extract_title(html) == "Guidance on Generative AI for Students"


def test_extract_title_falls_back_to_page_title():
    html = "<html><head><title>Fallback Title</title></head><body><p>No h1 here.</p></body></html>"
    assert extract_title(html) == "Fallback Title"


def _build_test_pdf_bytes(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_extract_text_from_pdf_bytes_reads_native_text():
    pdf_bytes = _build_test_pdf_bytes("Policy on Generative AI Use")
    text = extract_text_from_pdf_bytes(pdf_bytes)
    assert "Policy on Generative AI Use" in text


def test_extract_text_from_pdf_bytes_empty_pdf_returns_empty_string():
    doc = fitz.open()
    doc.new_page()
    pdf_bytes = doc.tobytes()
    doc.close()
    text = extract_text_from_pdf_bytes(pdf_bytes)
    assert text == ""


def test_extract_pdf_metadata_includes_page_count():
    pdf_bytes = _build_test_pdf_bytes("Some text")
    meta = extract_pdf_metadata(pdf_bytes)
    assert meta["page_count"] == 1
