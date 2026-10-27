"""Search terms used to flag and score candidate pages during discovery.

Terms are split into three tiers, because a single flat term list was found
(during real-world validation against Icelandic university sites) to create
false or low-value candidates -- see docs/candidate_discovery.md, "Known
limitations" and the Phase 2 Iceland correction notes:

* STRONG_TERMS -- unambiguous AI-specific vocabulary. candidate_discovery.py
  requires at least one strong-term match (in the URL, title, or text
  preview) before a fetched page is written out as a candidate at all --
  see score_candidate()'s gating in candidate_discovery.py.
* CONTEXTUAL_TERMS -- generic higher-ed vocabulary (exams, teaching,
  student guidance, ...) that is common on pages with nothing to do with
  AI. These can raise a score a little and are recorded in matched_terms
  for transparency, but a page matching ONLY contextual terms is never
  written out as a candidate on its own.
* POLICY_SIGNAL_TERMS -- words that specifically suggest an institutional
  policy/guidance document rather than a news item, research profile, or
  course page (policy, strategy, guideline, stefna, viðmið, leiðbein...).
  These give a transparent score boost and feed the inferred-category
  heuristic in candidate_discovery.py; they are not, by themselves, AI
  vocabulary (a "strategy" page with no AI term still needs a strong-term
  match to become a candidate at all).

Matching (see candidate_discovery.match_terms) requires a LEFT word
boundary immediately before each term but not necessarily after, so
Icelandic inflected/compound forms still match (e.g. "gervigreind" matches
inside "gervigreindarinnar"), while short, collision-prone terms like
"llm" do not match inside an unrelated word such as the surname "Kollmar"
(there is no left word boundary before "llm" in "Kollmar" -- "o" and "l"
are both word characters). See tests/test_candidate_discovery.py for the
regression test proving this.

English terms are the primary, high-confidence list. The Icelandic lists
are a best-effort starting set (not reviewed by a fluent speaker as part
of this implementation) -- a human researcher fluent in Icelandic should
review and extend them before discovery results are treated as complete.

These terms are used only to flag, score, and categorize candidates for
human review -- they never cause a page to be silently and permanently
included or excluded from the output CSV without a human looking at it;
see docs/candidate_discovery.md, "The human-review step (required)".
"""

from __future__ import annotations

STRONG_TERMS_ENGLISH: list[str] = [
    "artificial intelligence",
    "generative ai",
    "generative artificial intelligence",
    "chatgpt",
    "large language model",
    "llm",
    "ai policy",
    "ai guidance",
]

# Best-effort Icelandic terms -- see module docstring.
STRONG_TERMS_ICELANDIC: list[str] = [
    "gervigreind",  # artificial intelligence (stem -- matches inflected/compound forms)
    "spunagreind",  # generative AI (less common alternate rendering)
]

CONTEXTUAL_TERMS_ENGLISH: list[str] = [
    "teaching and learning",
    "assessment and examination",
    "examinations",
    "academic integrity",
    "academic misconduct",
    "student guidance",
    "staff guidance",
    "university policy",
]

CONTEXTUAL_TERMS_ICELANDIC: list[str] = [
    "kennsla og nám",  # teaching and learning
    "námsmat",  # assessment
    "próf",  # exam / test (also matches "prófessor" -- acceptable, since a
    # contextual term alone never creates a candidate; see module docstring)
    "prófareglur",  # examination rules
    "misferli í námi",  # academic misconduct
    "heiðarleiki í námi",  # academic integrity (lit. "honesty in study")
    "leiðbeiningar fyrir nemendur",  # guidance for students
    "leiðbeiningar fyrir starfsfólk",  # guidance for staff
    "reglur háskólans",  # university rules
]

POLICY_SIGNAL_TERMS_ENGLISH: list[str] = [
    "policy",
    "strategy",
    "guideline",  # left-boundary matching also catches "guidelines"
    "responsible use",
    "rule",  # also catches "rules"
]

POLICY_SIGNAL_TERMS_ICELANDIC: list[str] = [
    "stefn",  # stem for stefna/stefnu/stefnumörkun (policy/strategy, all case forms)
    "viðmið",  # guideline(s)/criteria -- already a bare stem
    "leiðbein",  # stem for leiðbeiningar/leiðbeinandi (guidance/guidelines/advisory)
]

STRONG_TERMS: list[str] = STRONG_TERMS_ENGLISH + STRONG_TERMS_ICELANDIC
CONTEXTUAL_TERMS: list[str] = CONTEXTUAL_TERMS_ENGLISH + CONTEXTUAL_TERMS_ICELANDIC
POLICY_SIGNAL_TERMS: list[str] = POLICY_SIGNAL_TERMS_ENGLISH + POLICY_SIGNAL_TERMS_ICELANDIC

# Broad net used only to decide which discovered URLs are worth fetching at
# all (see candidate_discovery.url_looks_relevant) -- NOT used for scoring
# or for the strong-term candidate gate.
ALL_SEARCH_TERMS: list[str] = STRONG_TERMS + CONTEXTUAL_TERMS + POLICY_SIGNAL_TERMS
