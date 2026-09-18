"""Tests for modeling.topic_diagnostics: the topic-by-university,
topic-by-document-type, and institution-dominance diagnostics that let a
reader tell a genuine cross-institution theme apart from a topic that's
really just picking up on one source's writing style or document type.
"""

from __future__ import annotations

from nordic_ai_policy_tracker.modeling.topic_diagnostics import (
    INSTITUTION_DOMINANCE_THRESHOLD,
    compute_institution_dominance,
    compute_topic_document_type_table,
    compute_topic_university_table,
)
from nordic_ai_policy_tracker.schemas import TopicChunk


def _chunk(document_id, university_id, topic_id, is_outlier=False):
    return TopicChunk(
        chunk_id=f"{document_id}_{topic_id}_{university_id}_{id(object())}",
        document_id=document_id,
        university_id=university_id,
        chunk_index=0,
        chunk_text="text",
        topic_id=topic_id,
        is_outlier=is_outlier,
    )


def _doc_row(document_id, university_id, university_name, document_type):
    return {
        "document_id": document_id,
        "university_id": university_id,
        "university_name": university_name,
        "document_type": document_type,
    }


DOCUMENT_ROWS = [
    _doc_row("doc_a", "uio_no", "University of Oslo", "institution_wide_policy"),
    _doc_row("doc_b", "uio_no", "University of Oslo", "student_guidance"),
    _doc_row("doc_c", "au_dk", "Aarhus University", "examination_guidance"),
    _doc_row("doc_d", "lund_se", "Lund University", "teaching_and_learning_guidance"),
]


def test_compute_topic_university_table_excludes_outliers():
    chunks = [
        _chunk("doc_a", "uio_no", topic_id=-1, is_outlier=True),
        _chunk("doc_a", "uio_no", topic_id=0),
        _chunk("doc_c", "au_dk", topic_id=0),
    ]
    table = compute_topic_university_table(chunks, DOCUMENT_ROWS)
    topic_ids = {row["topic_id"] for row in table}
    assert -1 not in topic_ids
    assert 0 in topic_ids


def test_compute_topic_university_table_percentages():
    # Topic 0: 3 chunks from uio_no, 1 from au_dk -> uio_no is 75% of topic 0.
    chunks = [_chunk("doc_a", "uio_no", topic_id=0) for _ in range(3)] + [
        _chunk("doc_c", "au_dk", topic_id=0)
    ]
    table = compute_topic_university_table(chunks, DOCUMENT_ROWS)
    uio_row = next(r for r in table if r["university_id"] == "uio_no")
    au_row = next(r for r in table if r["university_id"] == "au_dk")
    assert uio_row["chunk_count"] == 3
    assert uio_row["pct_of_topic"] == 75.0
    assert au_row["pct_of_topic"] == 25.0


def test_institution_dominance_flags_single_university_topic():
    # A topic made up almost entirely of one university's chunks must be
    # flagged (> INSTITUTION_DOMINANCE_THRESHOLD).
    chunks = [_chunk("doc_a", "uio_no", topic_id=0) for _ in range(9)] + [
        _chunk("doc_c", "au_dk", topic_id=0)
    ]
    summary = compute_institution_dominance(chunks, DOCUMENT_ROWS)
    topic0 = next(row for row in summary if row["topic_id"] == 0)
    assert topic0["dominant_university_id"] == "uio_no"
    assert topic0["dominant_university_share"] > INSTITUTION_DOMINANCE_THRESHOLD * 100
    assert topic0["institution_dominance_flag"] is True


def test_institution_dominance_does_not_flag_evenly_spread_topic():
    chunks = [
        _chunk("doc_a", "uio_no", topic_id=0),
        _chunk("doc_c", "au_dk", topic_id=0),
        _chunk("doc_d", "lund_se", topic_id=0),
    ]
    summary = compute_institution_dominance(chunks, DOCUMENT_ROWS)
    topic0 = next(row for row in summary if row["topic_id"] == 0)
    assert topic0["institution_dominance_flag"] is False
    assert topic0["n_universities"] == 3
    # An evenly-spread topic should have higher entropy than a
    # single-university topic.
    assert topic0["entropy"] > 0.0


def test_institution_dominance_entropy_zero_for_single_university():
    chunks = [_chunk("doc_a", "uio_no", topic_id=0) for _ in range(5)]
    summary = compute_institution_dominance(chunks, DOCUMENT_ROWS)
    topic0 = next(row for row in summary if row["topic_id"] == 0)
    assert topic0["entropy"] == 0.0
    assert topic0["n_universities"] == 1


def test_compute_topic_document_type_table_excludes_outliers_and_reports_shares():
    chunks = [
        _chunk("doc_a", "uio_no", topic_id=0),  # institution_wide_policy
        _chunk("doc_b", "uio_no", topic_id=0),  # student_guidance
        _chunk("doc_c", "au_dk", topic_id=-1, is_outlier=True),  # excluded
    ]
    table = compute_topic_document_type_table(chunks, DOCUMENT_ROWS)
    doc_types = {row["document_type"] for row in table}
    assert doc_types == {"institution_wide_policy", "student_guidance"}
    for row in table:
        assert row["pct_of_topic"] == 50.0


def test_diagnostics_handle_no_non_outlier_topics():
    chunks = [_chunk("doc_a", "uio_no", topic_id=-1, is_outlier=True)]
    assert compute_topic_university_table(chunks, DOCUMENT_ROWS) == []
    assert compute_institution_dominance(chunks, DOCUMENT_ROWS) == []
    assert compute_topic_document_type_table(chunks, DOCUMENT_ROWS) == []
