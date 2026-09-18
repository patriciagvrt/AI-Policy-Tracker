"""Tests for the SQLite access layer, focused on save_dimension_score() and
save_index_result() being idempotent per their identity key.

This directly guards against the bug found while investigating why the
Policy Matrix page showed each automated component score twice: both
functions used to be plain INSERTs, so re-running
scripts/calculate_indices.py (an ordinary, expected workflow -- e.g. the
rule-based pass, then again later with --include-human) silently
duplicated every row rather than replacing it.
"""

from __future__ import annotations

from datetime import UTC, datetime

from nordic_ai_policy_tracker.database import (
    init_db,
    list_dimension_scores,
    list_index_results,
    save_dimension_score,
    save_document,
    save_index_result,
)
from nordic_ai_policy_tracker.schemas import (
    CoderType,
    CollectionStatus,
    DimensionScore,
    ExtractionMethod,
    IndexKind,
    IndexResult,
    NordicCountry,
    PolicyDocument,
    TranslationStatus,
)


def _seed_document(db_path, document_id="doc1") -> None:
    """dimension_scores/index_results carry a FOREIGN KEY on document_id,
    so every test needs a matching documents row first.
    """
    save_document(
        db_path,
        PolicyDocument(
            document_id=document_id,
            university_id="test_uni",
            university_name="Test University",
            country=NordicCountry.SWEDEN,
            title="Test Policy",
            source_url="https://example.com/policy",
            retrieval_timestamp=datetime.now(UTC),
            analyzed_language="en",
            translation_status=TranslationStatus.ORIGINAL,
            document_type="institution_wide_policy",
            intended_audience="students",
            file_format="html",
            extraction_method=ExtractionMethod.HTML_HTTP,
            cleaned_text="Some cleaned text.",
            word_count=3,
            collection_status=CollectionStatus.COLLECTED,
        ),
    )


def _dimension_score(
    document_id="doc1",
    dimension_id="dim1",
    axis="restriction_enforcement",
    score=2,
    coder_id="rule_based_v1",
    coder_type=CoderType.RULE_BASED,
    coding_round=1,
) -> DimensionScore:
    return DimensionScore(
        document_id=document_id,
        dimension_id=dimension_id,
        axis=axis,
        score=score,
        evidence_passage="Evidence." if score > 0 else None,
        coder_id=coder_id,
        coder_type=coder_type,
        coding_timestamp=datetime.now(UTC),
        coding_round=coding_round,
    )


def _index_result(
    document_id="doc1",
    index_name=IndexKind.AUTOMATED_REI_HINT,
    raw_score=3.0,
    normalized_score=42.86,
    coder_type=CoderType.RULE_BASED,
    coding_round=1,
) -> IndexResult:
    return IndexResult(
        document_id=document_id,
        index_name=index_name,
        raw_score=raw_score,
        normalized_score=normalized_score,
        n_dimensions_total=7,
        n_dimensions_coded=7,
        n_dimensions_missing=0,
        component_scores={"dim1": 2},
        confidence=1.0,
        coder_type=coder_type,
        coding_round=coding_round,
    )


# --- save_dimension_score() idempotency -----------------------------------


def test_save_dimension_score_rerun_does_not_duplicate(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    _seed_document(db_path)
    score = _dimension_score()

    save_dimension_score(db_path, score)
    save_dimension_score(db_path, score)  # simulate re-running calculate_indices.py

    rows = list_dimension_scores(db_path, document_id="doc1")
    assert len(rows) == 1


def test_save_dimension_score_rerun_updates_the_value(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    _seed_document(db_path)
    save_dimension_score(db_path, _dimension_score(score=0))
    save_dimension_score(db_path, _dimension_score(score=2))  # corrected rule/re-run

    rows = list_dimension_scores(db_path, document_id="doc1")
    assert len(rows) == 1
    assert rows[0]["score"] == 2


def test_save_dimension_score_different_coder_id_gets_its_own_row(tmp_path):
    # A second human coder (future inter-coder reliability work) must not
    # overwrite the first coder's row.
    db_path = tmp_path / "test.db"
    init_db(db_path)
    _seed_document(db_path)
    save_dimension_score(
        db_path,
        _dimension_score(coder_id="patricia", coder_type=CoderType.HUMAN, score=2),
    )
    save_dimension_score(
        db_path,
        _dimension_score(coder_id="second_coder", coder_type=CoderType.HUMAN, score=1),
    )

    rows = list_dimension_scores(db_path, document_id="doc1")
    assert len(rows) == 2


def test_save_dimension_score_different_coding_round_gets_its_own_row(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    _seed_document(db_path)
    save_dimension_score(db_path, _dimension_score(coding_round=1, score=1))
    save_dimension_score(db_path, _dimension_score(coding_round=2, score=2))

    rows = list_dimension_scores(db_path, document_id="doc1")
    assert len(rows) == 2


# --- save_index_result() idempotency ---------------------------------------


def test_save_index_result_rerun_does_not_duplicate(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    _seed_document(db_path)
    result = _index_result()

    save_index_result(db_path, result)
    save_index_result(db_path, result)  # simulate re-running calculate_indices.py

    rows = list_index_results(db_path)
    assert len(rows) == 1


def test_save_index_result_rerun_updates_the_value(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    _seed_document(db_path)
    save_index_result(db_path, _index_result(raw_score=3.0, normalized_score=42.86))
    save_index_result(db_path, _index_result(raw_score=5.0, normalized_score=71.43))

    rows = list_index_results(db_path)
    assert len(rows) == 1
    assert rows[0]["raw_score"] == 5.0


def test_save_index_result_different_index_name_gets_its_own_row(tmp_path):
    # automated_rei_hint and automated_pisi_hint for the same document must
    # both be kept -- the identity key includes index_name.
    db_path = tmp_path / "test.db"
    init_db(db_path)
    _seed_document(db_path)
    save_index_result(db_path, _index_result(index_name=IndexKind.AUTOMATED_REI_HINT))
    save_index_result(db_path, _index_result(index_name=IndexKind.AUTOMATED_PISI_HINT))

    rows = list_index_results(db_path)
    assert len(rows) == 2


def test_save_index_result_automated_and_human_kinds_coexist(tmp_path):
    # Rerunning the automated pass must never touch/replace a human row for
    # the same document -- they differ in coder_type.
    db_path = tmp_path / "test.db"
    init_db(db_path)
    _seed_document(db_path)
    save_index_result(
        db_path,
        _index_result(index_name=IndexKind.AUTOMATED_REI_HINT, coder_type=CoderType.RULE_BASED),
    )
    save_index_result(
        db_path,
        _index_result(index_name=IndexKind.HUMAN_REI, coder_type=CoderType.HUMAN),
    )
    save_index_result(
        db_path,
        _index_result(index_name=IndexKind.AUTOMATED_REI_HINT, coder_type=CoderType.RULE_BASED),
    )  # re-run of the automated pass only

    rows = list_index_results(db_path)
    assert len(rows) == 2
    kinds = {r["index_name"] for r in rows}
    assert kinds == {"automated_rei_hint", "human_rei"}
