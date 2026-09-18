"""Tests for stable ID creation and content hashing."""

from __future__ import annotations

from nordic_ai_policy_tracker.utils.text_hashing import (
    compute_document_id,
    compute_text_hash,
    normalize_for_hashing,
)


def test_compute_document_id_is_deterministic():
    id1 = compute_document_id("lund_se", "https://www.staff.lu.se/policy.pdf")
    id2 = compute_document_id("lund_se", "https://www.staff.lu.se/policy.pdf")
    assert id1 == id2


def test_compute_document_id_differs_for_different_urls():
    id1 = compute_document_id("lund_se", "https://www.staff.lu.se/policy-a.pdf")
    id2 = compute_document_id("lund_se", "https://www.staff.lu.se/policy-b.pdf")
    assert id1 != id2


def test_compute_document_id_includes_university_prefix():
    doc_id = compute_document_id("lund_se", "https://example.edu/x")
    assert doc_id.startswith("lund_se_")


def test_compute_text_hash_stable_across_whitespace_differences():
    text1 = "Students   must  disclose AI use."
    text2 = "Students must disclose AI use."
    assert compute_text_hash(text1) == compute_text_hash(text2)


def test_compute_text_hash_differs_for_different_content():
    assert compute_text_hash("Text A") != compute_text_hash("Text B")


def test_normalize_for_hashing_collapses_whitespace():
    assert normalize_for_hashing("a   b\n\nc") == "a b c"
