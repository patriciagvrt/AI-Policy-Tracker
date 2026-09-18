"""Tests for duplicate and content-change detection."""

from __future__ import annotations

from datetime import UTC, datetime

from nordic_ai_policy_tracker.processing.deduplication import (
    find_exact_duplicates,
    has_content_changed,
    mark_duplicates,
)
from nordic_ai_policy_tracker.schemas import (
    CollectionStatus,
    ExtractionMethod,
    NordicCountry,
    PolicyDocument,
    TranslationStatus,
)


def _make_doc(document_id: str, text_hash: str | None) -> PolicyDocument:
    return PolicyDocument(
        document_id=document_id,
        university_id="fixture",
        university_name="Fixture University",
        country=NordicCountry.SWEDEN,
        title="Fixture Policy",
        source_url="https://example.edu/policy",
        retrieval_timestamp=datetime.now(UTC),
        analyzed_language="en",
        translation_status=TranslationStatus.UNKNOWN,
        document_type="institution-wide policy",
        intended_audience="students",
        file_format="html",
        extraction_method=ExtractionMethod.HTML_HTTP,
        text_hash=text_hash,
        collection_status=CollectionStatus.COLLECTED,
    )


def test_find_exact_duplicates_identifies_matching_hashes():
    docs = [_make_doc("a", "hash1"), _make_doc("b", "hash2"), _make_doc("c", "hash1")]
    duplicates = find_exact_duplicates(docs)
    assert duplicates == {"c": "a"}


def test_find_exact_duplicates_ignores_missing_hashes():
    docs = [_make_doc("a", None), _make_doc("b", None)]
    assert find_exact_duplicates(docs) == {}


def test_mark_duplicates_sets_duplicate_of_field():
    docs = [_make_doc("a", "hash1"), _make_doc("b", "hash1")]
    updated = mark_duplicates(docs)
    by_id = {d.document_id: d for d in updated}
    assert by_id["a"].duplicate_of is None
    assert by_id["b"].duplicate_of == "a"


def test_has_content_changed_true_when_hash_differs():
    assert has_content_changed("hash1", "hash2") is True


def test_has_content_changed_false_when_hash_matches():
    assert has_content_changed("hash1", "hash1") is False


def test_has_content_changed_true_when_previous_unknown():
    assert has_content_changed(None, "hash1") is True
