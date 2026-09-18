"""Tests for REI/PISI index construction: score boundaries, missing values,
unequal dimension counts, normalization, and the three index-kind
completeness gates (automated hint / human / validated).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from nordic_ai_policy_tracker.modeling.indices import (
    compute_automated_hint_for_axis,
    compute_automated_hints_for_document,
    compute_human_index_for_axis,
    compute_human_indices_for_document,
    compute_validated_index_for_axis,
    compute_validated_indices_for_document,
    sensitivity_analysis,
)
from nordic_ai_policy_tracker.schemas import CoderType, DimensionScore, IndexKind

CODING_DIMENSIONS_FIXTURE = {
    "dimensions": [
        {"id": "r1", "axis": "restriction_enforcement", "label": "R1"},
        {"id": "r2", "axis": "restriction_enforcement", "label": "R2"},
        {"id": "p1", "axis": "pedagogical_support", "label": "P1"},
        {"id": "p2", "axis": "pedagogical_support", "label": "P2"},
        {"id": "p3", "axis": "pedagogical_support", "label": "P3"},
    ]
}


def _score(
    document_id, dimension_id, axis, score, coder_type=CoderType.HUMAN, coding_round=1
) -> DimensionScore:
    return DimensionScore(
        document_id=document_id,
        dimension_id=dimension_id,
        axis=axis,
        score=score,
        evidence_passage="Evidence." if score > 0 else None,
        coder_id="patricia",
        coder_type=coder_type,
        coding_timestamp=datetime.now(UTC),
        coding_round=coding_round,
    )


# --- Automated hint: always computed, even from partial coverage ----------


def test_automated_hint_score_boundaries_zero_and_max():
    scores = [
        _score("doc1", "r1", "restriction_enforcement", 0, coder_type=CoderType.RULE_BASED),
        _score("doc1", "r2", "restriction_enforcement", 2, coder_type=CoderType.RULE_BASED),
    ]
    result = compute_automated_hint_for_axis(
        "doc1", "restriction_enforcement", scores, CODING_DIMENSIONS_FIXTURE
    )
    assert result.index_name == IndexKind.AUTOMATED_REI_HINT
    assert result.raw_score == 2
    assert result.normalized_score == 50.0  # 2 out of max 4 (2 dims * 2)
    assert result.n_dimensions_coded == 2
    assert result.n_dimensions_missing == 0


def test_automated_hint_missing_dimensions_not_silently_imputed_as_zero():
    # Only 1 of 2 REI dimensions coded.
    scores = [_score("doc1", "r1", "restriction_enforcement", 2, coder_type=CoderType.RULE_BASED)]
    result = compute_automated_hint_for_axis(
        "doc1", "restriction_enforcement", scores, CODING_DIMENSIONS_FIXTURE
    )
    assert result.n_dimensions_total == 2
    assert result.n_dimensions_coded == 1
    assert result.n_dimensions_missing == 1
    # Normalized against the ONE coded dimension's max (2), not against
    # both dimensions as if the missing one were 0.
    assert result.normalized_score == 100.0
    assert result.confidence == 0.5


def test_automated_hint_computed_even_from_partial_coverage_never_none():
    # Automated hints have NO completeness gate -- unlike human/validated.
    result = compute_automated_hint_for_axis(
        "doc1", "restriction_enforcement", [], CODING_DIMENSIONS_FIXTURE
    )
    assert result is not None
    assert result.raw_score == 0
    assert result.normalized_score == 0
    assert result.confidence == 0.0
    assert result.n_dimensions_coded == 0


def test_automated_hints_use_rule_based_coder_type_and_never_bare_names():
    rei, pisi = compute_automated_hints_for_document("doc1", [], CODING_DIMENSIONS_FIXTURE)
    assert rei.coder_type == CoderType.RULE_BASED
    assert rei.index_name == IndexKind.AUTOMATED_REI_HINT
    assert pisi.index_name == IndexKind.AUTOMATED_PISI_HINT
    # Never a bare "REI"/"PISI" string.
    assert rei.index_name != "REI"
    assert pisi.index_name != "PISI"


# --- Human index: only when the axis is COMPLETELY coded ------------------


def test_human_index_is_none_when_axis_incomplete():
    # Only 1 of 2 REI dimensions coded by a human.
    scores = [_score("doc1", "r1", "restriction_enforcement", 2)]
    result = compute_human_index_for_axis(
        "doc1", "restriction_enforcement", scores, CODING_DIMENSIONS_FIXTURE
    )
    assert result is None  # "Not yet human-coded" -- never a partial number


def test_human_index_computed_when_axis_complete():
    scores = [
        _score("doc1", "r1", "restriction_enforcement", 2),
        _score("doc1", "r2", "restriction_enforcement", 0),
    ]
    result = compute_human_index_for_axis(
        "doc1", "restriction_enforcement", scores, CODING_DIMENSIONS_FIXTURE
    )
    assert result is not None
    assert result.index_name == IndexKind.HUMAN_REI
    assert result.coder_type == CoderType.HUMAN
    assert result.n_dimensions_coded == 2
    assert result.confidence == 1.0


def test_human_indices_for_document_independent_per_axis():
    # REI fully coded, PISI only partially -- REI should return a result,
    # PISI should return None, independently.
    scores = [
        _score("doc1", "r1", "restriction_enforcement", 1),
        _score("doc1", "r2", "restriction_enforcement", 1),
        _score("doc1", "p1", "pedagogical_support", 2),
    ]
    rei, pisi = compute_human_indices_for_document("doc1", scores, CODING_DIMENSIONS_FIXTURE)
    assert rei is not None
    assert pisi is None


def test_human_index_ignores_rule_based_scores():
    # Rule-based scores must never count toward human completeness.
    scores = [
        _score("doc1", "r1", "restriction_enforcement", 2, coder_type=CoderType.RULE_BASED),
        _score("doc1", "r2", "restriction_enforcement", 2, coder_type=CoderType.RULE_BASED),
    ]
    result = compute_human_index_for_axis(
        "doc1", "restriction_enforcement", scores, CODING_DIMENSIONS_FIXTURE
    )
    assert result is None


# --- Validated index: only when a complete round-2+ recoding exists -------


def test_validated_index_is_none_with_no_recoding_round():
    # Complete round-1 human coding, but no round 2 -- not validated yet.
    scores = [
        _score("doc1", "r1", "restriction_enforcement", 1, coding_round=1),
        _score("doc1", "r2", "restriction_enforcement", 1, coding_round=1),
    ]
    result = compute_validated_index_for_axis(
        "doc1", "restriction_enforcement", scores, CODING_DIMENSIONS_FIXTURE
    )
    assert result is None


def test_validated_index_is_none_when_round_two_incomplete():
    scores = [
        _score("doc1", "r1", "restriction_enforcement", 1, coding_round=1),
        _score("doc1", "r2", "restriction_enforcement", 1, coding_round=1),
        _score("doc1", "r1", "restriction_enforcement", 1, coding_round=2),  # only r1 recoded
    ]
    result = compute_validated_index_for_axis(
        "doc1", "restriction_enforcement", scores, CODING_DIMENSIONS_FIXTURE
    )
    assert result is None


def test_validated_index_computed_once_round_two_is_complete():
    scores = [
        _score("doc1", "r1", "restriction_enforcement", 1, coding_round=1),
        _score("doc1", "r2", "restriction_enforcement", 1, coding_round=1),
        _score("doc1", "r1", "restriction_enforcement", 2, coding_round=2),
        _score("doc1", "r2", "restriction_enforcement", 2, coding_round=2),
    ]
    result = compute_validated_index_for_axis(
        "doc1", "restriction_enforcement", scores, CODING_DIMENSIONS_FIXTURE
    )
    assert result is not None
    assert result.index_name == IndexKind.VALIDATED_REI
    assert result.coding_round == 2
    assert result.normalized_score == 100.0  # uses round-2 scores (2, 2)


def test_validated_indices_for_document_independent_per_axis():
    scores = [
        _score("doc1", "r1", "restriction_enforcement", 1, coding_round=1),
        _score("doc1", "r2", "restriction_enforcement", 1, coding_round=1),
        _score("doc1", "r1", "restriction_enforcement", 1, coding_round=2),
        _score("doc1", "r2", "restriction_enforcement", 1, coding_round=2),
        # PISI only coded in round 1 -- no recoding, so no validated PISI.
        _score("doc1", "p1", "pedagogical_support", 1, coding_round=1),
        _score("doc1", "p2", "pedagogical_support", 1, coding_round=1),
        _score("doc1", "p3", "pedagogical_support", 1, coding_round=1),
    ]
    rei, pisi = compute_validated_indices_for_document("doc1", scores, CODING_DIMENSIONS_FIXTURE)
    assert rei is not None
    assert pisi is None


# --- Cross-cutting: independence, evidence requirement, sensitivity -------


def test_unequal_dimension_counts_between_axes():
    # REI has 2 dims, PISI has 3 -- confirm each axis uses its own total.
    rei, pisi = compute_human_indices_for_document(
        "doc1",
        [
            _score("doc1", "r1", "restriction_enforcement", 1),
            _score("doc1", "r2", "restriction_enforcement", 1),
            _score("doc1", "p1", "pedagogical_support", 2),
            _score("doc1", "p2", "pedagogical_support", 2),
            _score("doc1", "p3", "pedagogical_support", 2),
        ],
        CODING_DIMENSIONS_FIXTURE,
    )
    assert rei.n_dimensions_total == 2
    assert pisi.n_dimensions_total == 3
    assert rei.confidence == 1.0
    assert pisi.confidence == 1.0


def test_rei_and_pisi_never_combined_into_one_score():
    rei, pisi = compute_human_indices_for_document(
        "doc1",
        [
            _score("doc1", "r1", "restriction_enforcement", 2),
            _score("doc1", "r2", "restriction_enforcement", 2),
            _score("doc1", "p1", "pedagogical_support", 2),
            _score("doc1", "p2", "pedagogical_support", 2),
            _score("doc1", "p3", "pedagogical_support", 2),
        ],
        CODING_DIMENSIONS_FIXTURE,
    )
    # Both can be simultaneously at their maximum -- there is no shared
    # scale or subtraction between them.
    assert rei.normalized_score == 100.0
    assert pisi.normalized_score == 100.0
    assert rei.index_name == IndexKind.HUMAN_REI
    assert pisi.index_name == IndexKind.HUMAN_PISI


def test_dimension_score_requires_evidence_for_nonzero_score():
    with pytest.raises(ValueError):
        DimensionScore(
            document_id="doc1",
            dimension_id="r1",
            axis="restriction_enforcement",
            score=1,
            evidence_passage=None,
            coder_id="patricia",
            coder_type=CoderType.HUMAN,
            coding_timestamp=datetime.now(UTC),
        )


def test_sensitivity_analysis_returns_baseline_and_alternative():
    scores = [
        _score("doc1", "r1", "restriction_enforcement", 2, coder_type=CoderType.RULE_BASED),
        _score("doc1", "r2", "restriction_enforcement", 0, coder_type=CoderType.RULE_BASED),
    ]
    results = sensitivity_analysis(
        "doc1",
        scores,
        CODING_DIMENSIONS_FIXTURE,
        alternative_weight_sets={"r1_double_weight": {"r1": 2.0, "r2": 1.0}},
    )
    assert "equal_baseline" in results
    assert "r1_double_weight" in results
    baseline_rei, _ = results["equal_baseline"]
    weighted_rei, _ = results["r1_double_weight"]
    # Weighting r1 (score=2) more heavily than r2 (score=0) should raise
    # the normalized score relative to equal weighting.
    assert weighted_rei.normalized_score > baseline_rei.normalized_score
