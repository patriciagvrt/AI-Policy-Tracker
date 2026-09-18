"""Human-coding validation utilities: intra-coder reliability now,
inter-coder reliability once a second coder joins.

For the pilot (a single coder), this module implements the intra-coder
check: the same coder recodes a subset of documents after a time interval,
and we compare round 1 vs round 2 scores per dimension.

Weighted Cohen's kappa (for two coders on ordinal 0-2 data) is implemented
here now so it is ready the moment a second coder's data exists, but this
module never fabricates a kappa value -- every function that needs two
coders' data raises if it isn't given real data for both.
"""

from __future__ import annotations

from dataclasses import dataclass

from sklearn.metrics import cohen_kappa_score

from nordic_ai_policy_tracker.schemas import DimensionScore


@dataclass
class IntraCoderComparison:
    document_id: str
    dimension_id: str
    round_1_score: int
    round_2_score: int
    agree: bool
    round_1_evidence: str | None
    round_2_evidence: str | None


def compare_coding_rounds(
    round_1_scores: list[DimensionScore], round_2_scores: list[DimensionScore]
) -> list[IntraCoderComparison]:
    """Pair up round-1 and round-2 scores for the same (document, dimension)
    and return a per-pair comparison. Documents/dimensions present in only
    one round are skipped (and should be reported separately as incomplete
    coverage, not silently ignored -- see scripts output).
    """
    round_2_lookup = {(s.document_id, s.dimension_id): s for s in round_2_scores}
    comparisons: list[IntraCoderComparison] = []
    for r1 in round_1_scores:
        key = (r1.document_id, r1.dimension_id)
        r2 = round_2_lookup.get(key)
        if r2 is None:
            continue
        comparisons.append(
            IntraCoderComparison(
                document_id=r1.document_id,
                dimension_id=r1.dimension_id,
                round_1_score=r1.score,
                round_2_score=r2.score,
                agree=(r1.score == r2.score),
                round_1_evidence=r1.evidence_passage,
                round_2_evidence=r2.evidence_passage,
            )
        )
    return comparisons


def intra_coder_agreement_rate(comparisons: list[IntraCoderComparison]) -> float | None:
    """Simple percent-agreement across all compared (document, dimension) pairs.

    Returns None if there is nothing to compare yet (e.g. round 2 has not
    been conducted). This is a plain agreement rate, not a chance-corrected
    statistic -- weighted kappa (below) is the chance-corrected version,
    reserved for the inter-coder case once a second coder exists, per the
    project brief's instruction not to claim intra-coder consistency
    removes individual coder bias.
    """
    if not comparisons:
        return None
    agreements = sum(1 for c in comparisons if c.agree)
    return round(agreements / len(comparisons), 3)


def weighted_cohens_kappa(coder_a_scores: list[int], coder_b_scores: list[int]) -> float:
    """Weighted (quadratic) Cohen's kappa for two coders' ordinal 0-2 scores.

    This is the statistic documented as the PLANNED inter-coder reliability
    measure once a second coder joins the project (see docs/methodology.md
    and docs/coding_guide.md). It is implemented and tested now (see
    tests/test_indicators.py-adjacent validation tests) using synthetic
    inputs, but is never called by the pilot's own reporting scripts with
    real data, since this pilot has only one coder. Calling it with
    mismatched-length lists raises ValueError, since silently truncating
    to the shorter list would misrepresent the comparison.
    """
    if len(coder_a_scores) != len(coder_b_scores):
        raise ValueError("coder_a_scores and coder_b_scores must be the same length")
    if len(coder_a_scores) == 0:
        raise ValueError("Cannot compute kappa on empty score lists")
    return float(cohen_kappa_score(coder_a_scores, coder_b_scores, weights="quadratic"))
