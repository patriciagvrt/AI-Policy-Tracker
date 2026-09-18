"""Rule-based indicator assistance.

This module does NOT assign final ordinal (0/1/2) scores. Its job is
narrower and more honest about what keyword matching can and can't do: given
a document and a dimension's keyword hints (config/coding_dimensions.yaml),
find candidate sentences, and flag whether each candidate sentence looks
negated, hedged, or otherwise NOT a straightforward endorsement of the
concept -- so a human coder (or a future supervised classifier) has a
shortlist to review, not a verdict to trust blindly.

The central example from the project brief is handled directly:
    "AI detectors are unreliable and should not be used as the sole basis
     for disciplinary action"
This sentence contains the keywords "AI detector" and "disciplinary
action", but describes detectors critically and prohibits relying on them
-- it is not evidence of surveillance endorsement. find_candidate_evidence()
below flags this sentence as `polarity="negative_or_hedged"` rather than
silently miscounting it as a hit for the ai_detection_surveillance
dimension.

Rule-based scores, when computed, are stored with coder_type="rule_based"
and are never merged into the same score as coder_type="human" -- see
schemas.DimensionScore.coder_type and modeling/indices.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from nordic_ai_policy_tracker.processing.segmentation import split_into_sentences

# Words/phrases that, when they appear in the same sentence as a keyword
# hint, suggest the sentence is negating, criticizing, or hedging the
# concept rather than endorsing/describing its institutional presence.
NEGATION_MARKERS = [
    "not be used",
    "should not",
    "must not",
    "shall not",
    "unreliable",
    "is not required",
    "no longer",
    "without",
    "rather than",
    "instead of",
    "does not mean",
    "is not a substitute",
    "cannot replace",
    "not intended to",
    "we do not",
    "avoid using",
]

# Phrases suggesting the sentence is describing a hypothetical, an
# exception, or a quoted/reported view rather than a direct institutional
# statement.
HEDGE_MARKERS = [
    "for example",
    "in some cases",
    "may vary by course",
    "according to",
    "some students",
    "some staff",
    "hypothetical",
    "e.g.",
]


@dataclass
class CandidateEvidence:
    dimension_id: str
    sentence: str
    matched_keyword: str
    polarity: str  # "plain_match" | "negative_or_hedged"
    sentence_index: int


def _sentence_matches_keyword(sentence: str, keyword: str) -> bool:
    pattern = r"\b" + re.escape(keyword.lower()) + r"\b"
    return re.search(pattern, sentence.lower()) is not None


def classify_polarity(sentence: str) -> str:
    """Return "negative_or_hedged" if the sentence contains a negation or
    hedging marker, else "plain_match".

    This is intentionally a coarse first-pass signal, not a full stance
    classifier. It exists to route sentences to a human coder's attention,
    not to auto-resolve them -- see the module docstring.
    """
    lowered = sentence.lower()
    if any(marker in lowered for marker in NEGATION_MARKERS):
        return "negative_or_hedged"
    if any(marker in lowered for marker in HEDGE_MARKERS):
        return "negative_or_hedged"
    return "plain_match"


def find_candidate_evidence(
    text: str, dimension_id: str, keyword_hints: list[str]
) -> list[CandidateEvidence]:
    """Scan `text` for sentences containing any of `keyword_hints`, and
    classify each as a plain match or a likely negation/hedge.

    Returns one CandidateEvidence per (sentence, matched keyword) pair --
    a sentence matching two keywords produces two entries, since each is
    a separate piece of potential evidence.
    """
    sentences = split_into_sentences(text)
    results: list[CandidateEvidence] = []
    for idx, sentence in enumerate(sentences):
        for keyword in keyword_hints:
            if _sentence_matches_keyword(sentence, keyword):
                results.append(
                    CandidateEvidence(
                        dimension_id=dimension_id,
                        sentence=sentence,
                        matched_keyword=keyword,
                        polarity=classify_polarity(sentence),
                        sentence_index=idx,
                    )
                )
    return results


def suggest_rule_based_score(candidates: list[CandidateEvidence]) -> int:
    """A conservative, transparent suggestion for a rule-based score,
    computed ONLY from plain_match candidates (negated/hedged candidates
    are excluded from scoring, though they are still returned by
    find_candidate_evidence for a human to see).

    This is deliberately simple: 0 plain matches -> 0, 1 plain match -> 1,
    2+ plain matches -> 2. It is a starting hypothesis for the human coder,
    stored separately as coder_type="rule_based", never a replacement for
    the human's own reading of the passage.
    """
    plain_matches = [c for c in candidates if c.polarity == "plain_match"]
    if len(plain_matches) == 0:
        return 0
    if len(plain_matches) == 1:
        return 1
    return 2
