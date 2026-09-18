"""REI and PISI index construction.

Both indices are built the same way, parameterized by which dimensions
belong to which axis (config/coding_dimensions.yaml):

  raw_score        = sum of available component scores (each 0-2)
  max_possible      = 2 * n_dimensions_total (if every dimension were coded as "emphasized")
  normalized_score  = 100 * raw_score / (2 * n_dimensions_coded)   <- normalized against
                       dimensions actually coded, not assumed-zero missing ones
  confidence        = n_dimensions_coded / n_dimensions_total

Two design choices worth calling out (both directly from the project brief):

1. Missing dimensions are NEVER silently treated as 0. A document with 4 of
   7 REI dimensions coded gets its normalized_score computed over those 4,
   plus a `confidence` of 4/7 so it's visibly less certain than a document
   with all 7 coded. Silently imputing missing=0 would make thin
   coverage look identical to genuine absence, which is exactly the kind
   of false precision this project is trying to avoid.

2. REI and PISI are never combined into a single number. Two separate
   IndexResult objects come out of the compute_* functions below; nothing
   in this module adds them together, subtracts one from the other, or
   otherwise collapses them onto one scale.

A THIRD design choice, added by the project's compliance correction, sits
on top of both of the above: this module never returns one generic "REI"/
"PISI" result. Every result is explicitly one of three KINDS
(nordic_ai_policy_tracker.schemas.IndexKind), each with different
completeness requirements:

- compute_automated_hint_for_axis(): a rule-based, exploratory hint.
  Computed from whatever rule-based dimension coverage exists, even if
  partial -- it is a research aid, not a claim about the document, so
  partial coverage is fine as long as `confidence` reflects it honestly.
- compute_human_index_for_axis(): computed ONLY from a human coder's
  COMPLETE annotation of every dimension in that axis, for one coding
  round. Returns None (not a low-confidence number) if any dimension in
  the axis is uncoded -- callers must treat None as "not yet
  human-coded", never as zero.
- compute_validated_index_for_axis(): a human index that has additionally
  passed a validation step. For this pilot, "validated" means a complete,
  independent SECOND coding round (round >= 2) exists for the same
  document and axis (the project's intra-coder recoding check), which the
  function verifies before returning anything. Returns None if no such
  round exists yet -- which, for this pilot, is every document today: no
  recoding round has been run.
"""

from __future__ import annotations

from nordic_ai_policy_tracker.schemas import CoderType, DimensionScore, IndexKind, IndexResult

SCALE_MAX = 100

_AXIS_TO_KIND = {
    ("restriction_enforcement", "automated_hint"): IndexKind.AUTOMATED_REI_HINT,
    ("pedagogical_support", "automated_hint"): IndexKind.AUTOMATED_PISI_HINT,
    ("restriction_enforcement", "human"): IndexKind.HUMAN_REI,
    ("pedagogical_support", "human"): IndexKind.HUMAN_PISI,
    ("restriction_enforcement", "validated"): IndexKind.VALIDATED_REI,
    ("pedagogical_support", "validated"): IndexKind.VALIDATED_PISI,
}


def _dimension_ids_for_axis(coding_dimensions: dict, axis: str) -> list[str]:
    return [d["id"] for d in coding_dimensions["dimensions"] if d["axis"] == axis]


def _compute_raw_index(
    document_id: str,
    axis: str,
    index_name: IndexKind,
    scores: list[DimensionScore],
    coding_dimensions: dict,
    coder_type: CoderType,
    coding_round: int,
    weights: dict[str, float] | None = None,
) -> IndexResult:
    """Shared scoring math for one axis, given an already-filtered coder_type
    and coding_round. This is an internal helper -- callers should use one
    of the three gated compute_*_for_axis functions below instead, since
    those are what enforce the human/validated completeness rules.
    """
    all_dimension_ids = _dimension_ids_for_axis(coding_dimensions, axis)
    weights = weights or {dim_id: 1.0 for dim_id in all_dimension_ids}

    relevant_scores = {
        s.dimension_id: s.score
        for s in scores
        if s.document_id == document_id
        and s.axis == axis
        and s.coder_type == coder_type
        and s.coding_round == coding_round
    }

    coded_dimension_ids = [d for d in all_dimension_ids if d in relevant_scores]
    n_total = len(all_dimension_ids)
    n_coded = len(coded_dimension_ids)
    n_missing = n_total - n_coded

    if n_coded == 0:
        raw_score = 0.0
        normalized_score = 0.0
    else:
        weighted_sum = sum(relevant_scores[d] * weights.get(d, 1.0) for d in coded_dimension_ids)
        weight_sum = sum(weights.get(d, 1.0) for d in coded_dimension_ids)
        raw_score = weighted_sum
        # Normalize against the max possible score (2) times the total
        # weight of *coded* dimensions -- so confidence and normalized_score
        # are reported separately rather than conflated.
        max_possible = 2 * weight_sum
        normalized_score = (weighted_sum / max_possible) * SCALE_MAX if max_possible > 0 else 0.0

    weighting_scheme = "equal" if all(w == 1.0 for w in weights.values()) else "custom"

    return IndexResult(
        document_id=document_id,
        index_name=index_name,
        raw_score=raw_score,
        normalized_score=round(normalized_score, 2),
        n_dimensions_total=n_total,
        n_dimensions_coded=n_coded,
        n_dimensions_missing=n_missing,
        component_scores={d: relevant_scores[d] for d in coded_dimension_ids},
        weighting_scheme=weighting_scheme,
        confidence=round(n_coded / n_total, 3) if n_total > 0 else 0.0,
        coder_type=coder_type,
        coding_round=coding_round,
    )


def compute_automated_hint_for_axis(
    document_id: str,
    axis: str,
    scores: list[DimensionScore],
    coding_dimensions: dict,
    weights: dict[str, float] | None = None,
) -> IndexResult:
    """Always computes an automated (rule-based) hint, even from partial
    coverage -- confidence reflects how much of the axis the rule-based
    layer actually found evidence for. Never presented as the researcher's
    own interpretation; see dashboard/components/labels.py.
    """
    index_name = _AXIS_TO_KIND[(axis, "automated_hint")]
    return _compute_raw_index(
        document_id,
        axis,
        index_name,
        scores,
        coding_dimensions,
        CoderType.RULE_BASED,
        coding_round=1,
        weights=weights,
    )


def compute_human_index_for_axis(
    document_id: str,
    axis: str,
    scores: list[DimensionScore],
    coding_dimensions: dict,
    coding_round: int = 1,
    weights: dict[str, float] | None = None,
) -> IndexResult | None:
    """Computes a human-coded index ONLY if every dimension in this axis has
    a human score for this document and coding_round. Returns None
    otherwise -- callers (scripts/calculate_indices.py, the dashboard) must
    treat None as "not yet human-coded", not as a zero or a partial score.
    """
    all_dimension_ids = _dimension_ids_for_axis(coding_dimensions, axis)
    coded_ids = {
        s.dimension_id
        for s in scores
        if s.document_id == document_id
        and s.axis == axis
        and s.coder_type == CoderType.HUMAN
        and s.coding_round == coding_round
    }
    if not all_dimension_ids or not set(all_dimension_ids).issubset(coded_ids):
        return None

    index_name = _AXIS_TO_KIND[(axis, "human")]
    return _compute_raw_index(
        document_id,
        axis,
        index_name,
        scores,
        coding_dimensions,
        CoderType.HUMAN,
        coding_round=coding_round,
        weights=weights,
    )


def compute_validated_index_for_axis(
    document_id: str,
    axis: str,
    scores: list[DimensionScore],
    coding_dimensions: dict,
    weights: dict[str, float] | None = None,
    min_validation_round: int = 2,
) -> IndexResult | None:
    """Computes a validated index ONLY if a complete, independent recoding
    round (coding_round >= min_validation_round, default 2 -- this
    project's intra-coder recoding check) exists for this document/axis.

    For this pilot, that means this function returns None for every
    document today: no second coding round has been run yet. It will
    start returning a result the first time Patricia completes a full
    round-2 recoding of a document's axis; nothing else (agreement
    thresholds, a second independent coder) is required for this
    single-coder pilot, but a future inter-coder-reliability pass could
    tighten this gate without changing its return contract.
    """
    all_dimension_ids = _dimension_ids_for_axis(coding_dimensions, axis)
    rounds_present = {
        s.coding_round
        for s in scores
        if s.document_id == document_id and s.axis == axis and s.coder_type == CoderType.HUMAN
    }
    candidate_rounds = sorted(r for r in rounds_present if r >= min_validation_round)
    for round_n in reversed(candidate_rounds):
        coded_ids = {
            s.dimension_id
            for s in scores
            if s.document_id == document_id
            and s.axis == axis
            and s.coder_type == CoderType.HUMAN
            and s.coding_round == round_n
        }
        if all_dimension_ids and set(all_dimension_ids).issubset(coded_ids):
            index_name = _AXIS_TO_KIND[(axis, "validated")]
            return _compute_raw_index(
                document_id,
                axis,
                index_name,
                scores,
                coding_dimensions,
                CoderType.HUMAN,
                coding_round=round_n,
                weights=weights,
            )
    return None


def compute_automated_hints_for_document(
    document_id: str,
    scores: list[DimensionScore],
    coding_dimensions: dict,
    rei_weights: dict[str, float] | None = None,
    pisi_weights: dict[str, float] | None = None,
) -> tuple[IndexResult, IndexResult]:
    """Convenience wrapper returning (REI hint, PISI hint) for one document.
    Always returns two results (automated hints have no completeness gate).
    """
    rei = compute_automated_hint_for_axis(
        document_id, "restriction_enforcement", scores, coding_dimensions, rei_weights
    )
    pisi = compute_automated_hint_for_axis(
        document_id, "pedagogical_support", scores, coding_dimensions, pisi_weights
    )
    return rei, pisi


def compute_human_indices_for_document(
    document_id: str,
    scores: list[DimensionScore],
    coding_dimensions: dict,
    coding_round: int = 1,
    rei_weights: dict[str, float] | None = None,
    pisi_weights: dict[str, float] | None = None,
) -> tuple[IndexResult | None, IndexResult | None]:
    """Convenience wrapper returning (REI, PISI) human results for one
    document -- either element may be None if that axis isn't fully coded.
    """
    rei = compute_human_index_for_axis(
        document_id, "restriction_enforcement", scores, coding_dimensions, coding_round, rei_weights
    )
    pisi = compute_human_index_for_axis(
        document_id, "pedagogical_support", scores, coding_dimensions, coding_round, pisi_weights
    )
    return rei, pisi


def compute_validated_indices_for_document(
    document_id: str,
    scores: list[DimensionScore],
    coding_dimensions: dict,
    rei_weights: dict[str, float] | None = None,
    pisi_weights: dict[str, float] | None = None,
    min_validation_round: int = 2,
) -> tuple[IndexResult | None, IndexResult | None]:
    """Convenience wrapper returning (REI, PISI) validated results for one
    document -- either element may be None if no round-2+ recoding exists
    yet for that axis.
    """
    rei = compute_validated_index_for_axis(
        document_id,
        "restriction_enforcement",
        scores,
        coding_dimensions,
        rei_weights,
        min_validation_round,
    )
    pisi = compute_validated_index_for_axis(
        document_id,
        "pedagogical_support",
        scores,
        coding_dimensions,
        pisi_weights,
        min_validation_round,
    )
    return rei, pisi


def sensitivity_analysis(
    document_id: str,
    scores: list[DimensionScore],
    coding_dimensions: dict,
    alternative_weight_sets: dict[str, dict[str, float]],
) -> dict[str, tuple[IndexResult, IndexResult]]:
    """Recompute the AUTOMATED HINT under one or more alternative weighting
    schemes, so a reader can see how much the hint moves under a different
    (documented, not arbitrary-and-hidden) set of weights.

    Sensitivity analysis is run against the automated hint specifically,
    because it is the only index kind guaranteed to exist for every
    collected document regardless of human-coding progress; re-run it
    against compute_human_indices_for_document's output once human coding
    is complete, if a sensitivity check on the validated numbers is
    wanted.

    Args:
        alternative_weight_sets: {scheme_name: {dimension_id: weight}}.
            Each scheme's weights are applied to whichever axis its
            dimension IDs belong to; a scheme may cover REI dimensions,
            PISI dimensions, or both.

    Returns:
        {"equal_baseline": (rei, pisi), scheme_name: (rei, pisi), ...}
    """
    results: dict[str, tuple[IndexResult, IndexResult]] = {
        "equal_baseline": compute_automated_hints_for_document(
            document_id, scores, coding_dimensions
        )
    }
    for scheme_name, weights in alternative_weight_sets.items():
        rei_dims = set(_dimension_ids_for_axis(coding_dimensions, "restriction_enforcement"))
        pisi_dims = set(_dimension_ids_for_axis(coding_dimensions, "pedagogical_support"))
        rei_weights = {k: v for k, v in weights.items() if k in rei_dims} or None
        pisi_weights = {k: v for k, v in weights.items() if k in pisi_dims} or None
        results[scheme_name] = compute_automated_hints_for_document(
            document_id, scores, coding_dimensions, rei_weights, pisi_weights
        )
    return results
