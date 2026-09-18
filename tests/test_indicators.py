"""Tests for the rule-based, negation-sensitive indicator assistance layer.

The critical test here is test_negation_example_from_brief, which encodes
exactly the example given in the project requirements: a sentence
mentioning "AI detectors" and "disciplinary action" that actually argues
AGAINST relying on detection, and must not be scored as an endorsement of
surveillance.
"""

from __future__ import annotations

from pathlib import Path

from nordic_ai_policy_tracker.modeling.indicators import (
    classify_polarity,
    find_candidate_evidence,
    suggest_rule_based_score,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_classify_polarity_flags_negation():
    sentence = "AI detectors are unreliable and should not be used as the sole basis for disciplinary action."
    assert classify_polarity(sentence) == "negative_or_hedged"


def test_classify_polarity_plain_match_for_direct_statement():
    sentence = "The university uses AI detection software to review submitted assignments."
    assert classify_polarity(sentence) == "plain_match"


def test_negation_example_from_brief_not_scored_as_surveillance_endorsement():
    text = (FIXTURES_DIR / "sample_policy.txt").read_text(encoding="utf-8")
    candidates = find_candidate_evidence(
        text,
        dimension_id="ai_detection_surveillance",
        keyword_hints=["AI detector", "disciplinary action"],
    )
    # Both keywords should be found (the sentence contains both phrases)...
    assert len(candidates) >= 1
    # ...but every match on this sentence must be flagged as negative/hedged.
    for c in candidates:
        if "unreliable" in c.sentence.lower():
            assert c.polarity == "negative_or_hedged"

    # The conservative rule-based score should NOT credit this sentence as
    # evidence of surveillance endorsement (0 plain matches -> score 0).
    plain_matches = [c for c in candidates if c.polarity == "plain_match"]
    assert plain_matches == []
    assert suggest_rule_based_score(candidates) == 0


def test_find_candidate_evidence_plain_match_scores_present():
    text = "Staff support sessions are offered through the Teaching Development Office."
    candidates = find_candidate_evidence(
        text, dimension_id="staff_support", keyword_hints=["staff support"]
    )
    assert len(candidates) == 1
    assert candidates[0].polarity == "plain_match"
    assert suggest_rule_based_score(candidates) == 1


def test_suggest_rule_based_score_boundaries():
    from nordic_ai_policy_tracker.modeling.indicators import CandidateEvidence

    no_match: list[CandidateEvidence] = []
    one_match = [CandidateEvidence("d", "s", "k", "plain_match", 0)]
    two_matches = [
        CandidateEvidence("d", "s1", "k", "plain_match", 0),
        CandidateEvidence("d", "s2", "k", "plain_match", 1),
    ]
    assert suggest_rule_based_score(no_match) == 0
    assert suggest_rule_based_score(one_match) == 1
    assert suggest_rule_based_score(two_matches) == 2


def test_find_candidate_evidence_hedge_marker_detected():
    text = "For example, some students may use AI literacy resources provided by the library."
    candidates = find_candidate_evidence(
        text, dimension_id="ai_literacy", keyword_hints=["AI literacy"]
    )
    assert len(candidates) == 1
    assert candidates[0].polarity == "negative_or_hedged"
