"""Shared disclaimer / labeling text, so the same wording appears
everywhere it's needed rather than drifting between pages.
"""

PILOT_DISCLAIMER = (
    "**This is a five-university pilot** (one institution per Nordic country: "
    "Sweden, Norway, Denmark, Finland, Iceland). It tests the data pipeline "
    "end to end. It is **not** a representative sample of any national "
    "higher-education system, and results describe only the documents "
    "actually collected here."
)

# --- Index-kind disclaimers (automated hint / human / validated) -----------
#
# These three are deliberately different in tone. The automated one warns
# a reader away from treating the number as anyone's interpretation. The
# human one is neutral, factual framing. The "not yet" message is what
# every page shows in place of a number when no human coding exists --
# never a silent fallback to the automated hint.

AUTOMATED_HINT_DISCLAIMER = (
    "**Automated exploratory hint -- not human-coded.** These "
    "`automated_*_hint` values come from keyword/negation pattern matching "
    "(see `modeling/indicators.py`). They are a starting hypothesis for a "
    "human coder to check, never the researcher's own interpretation of the "
    "document, and are never displayed as if they were REI/PISI proper. See "
    "`docs/coding_guide.md`."
)

# Kept for backward compatibility with any code/tests still importing the
# old name; identical wording to AUTOMATED_HINT_DISCLAIMER.
RULE_BASED_DISCLAIMER = AUTOMATED_HINT_DISCLAIMER

HUMAN_INDEX_DISCLAIMER = (
    "**Human-coded index.** Computed only from this pilot's sole human "
    "coder's (Patricia's) complete annotation of every dimension in this "
    "axis. No intercoder reliability is claimed for a single-coder pilot; "
    "see `docs/methodology.md` and `docs/limitations.md`."
)

VALIDATED_INDEX_DISCLAIMER = (
    "**Validated index.** A human-coded index that has additionally passed "
    "an intra-coder recoding check (a complete, independent second coding "
    "round). See `docs/methodology.md`."
)

NOT_YET_HUMAN_CODED_MESSAGE = (
    "**Not yet human-coded.** No complete human annotation exists yet for "
    "this axis/document, so no human-coded index is shown here -- this is "
    "not the same as a score of zero. An automated exploratory hint may be "
    "available separately; it is never substituted here automatically. See "
    "`dashboard/pages/7_Annotation.py` to begin coding."
)

EMPTY_POLICY_MATRIX_MESSAGE = (
    "**No human-coded data yet.** The Policy Matrix's default view shows "
    "human-coded indices, and none exist yet for this pilot -- Patricia, "
    "this project's sole human coder, has not yet completed annotation for "
    "any document. This page intentionally shows an empty plot rather than "
    "silently substituting automated exploratory hints. Switch to "
    '"Automated exploratory hints" above to see the rule-based suggestions '
    "instead, or go to the Annotation page to begin human coding."
)

# --- Topic-model (BERTopic / TF-IDF fallback) disclaimer --------------------

BERTOPIC_DISCLAIMER = (
    "**Experimental -- read `docs/methodology.md` before interpreting.** "
    "Topics were discovered from a very small corpus (this pilot's chunks "
    "from 4 collected documents), so results are not stable or "
    "generalizable, and are never used as evidence for REI/PISI scores. "
    "In addition: this pilot's sandbox environment could not download the "
    "configured sentence-transformer model (no network path to "
    "huggingface.co), so the current run used a TF-IDF fallback embedding "
    "instead of true semantic embeddings -- see the `topic_method`, "
    "`topic_status`, and `semantic_embeddings_used` fields below. **This is "
    "not the final BERTopic analysis.** The topic model should be re-run "
    "locally (`python scripts/train_topics.py`) with network access to "
    "huggingface.co so the configured sentence-transformer model can "
    "actually be used, before these topics are treated as anything more "
    "than a pipeline smoke test."
)

TFIDF_FALLBACK_FIELD_NOTE = (
    "`topic_method=tfidf_fallback`, `topic_status=experimental`, "
    "`semantic_embeddings_used=false` -- these fields are stored with every "
    "topic-model run so a reader can tell, without re-reading logs, which "
    "embedding actually produced a given topic assignment."
)

NO_RANKING_DISCLAIMER = (
    "REI and PISI are two independent axes, not one quality scale. A "
    "university can score high on both, low on both, or high on one and "
    "low on the other -- none of these is 'better' or 'worse'. This "
    "project does not rank institutions."
)
