#!/usr/bin/env python
"""Stage 4 script: compute this project's three index KINDS -- automated
exploratory hints, human-coded indices, and validated indices -- and store
each under its own IndexKind name (never a bare "REI"/"PISI"), never
blending one kind into another.

- automated_*_hint: always computed for every collected document, from
  whatever rule-based dimension coverage exists (even partial). This is a
  research aid, never the researcher's own interpretation -- see
  dashboard/components/labels.py.
- human_*: computed ONLY when a document's axis has a COMPLETE human
  annotation for a given coding round (every dimension in that axis
  coded). Incomplete axes produce no human_* row at all -- see
  modeling/indices.compute_human_index_for_axis.
- validated_*: computed ONLY when a complete, independent round-2+
  recoding exists for that document/axis (this pilot's intra-coder
  reliability check). For this pilot, that is true for zero documents
  today, since no recoding round has been run yet.

Human coding is a separate, manual step (see the annotation template at
data/annotations/annotation_template.csv and
dashboard/pages/7_Annotation.py) that the pilot's sole human coder
(Patricia) has not yet performed as of this script being written. This
script never fabricates human or validated results to fill that gap.

Usage:
    python scripts/calculate_indices.py
    python scripts/calculate_indices.py --include-human --human-csv path/to/coded.csv
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

import pandas as pd  # noqa: E402

from nordic_ai_policy_tracker.config import (  # noqa: E402
    get_coding_dimensions,
    get_settings,
    resolve_path,
)
from nordic_ai_policy_tracker.database import (  # noqa: E402
    list_documents,
    save_dimension_score,
    save_index_result,
)
from nordic_ai_policy_tracker.modeling.indicators import (  # noqa: E402
    find_candidate_evidence,
    suggest_rule_based_score,
)
from nordic_ai_policy_tracker.modeling.indices import (  # noqa: E402
    compute_automated_hints_for_document,
    compute_human_indices_for_document,
    compute_validated_indices_for_document,
)
from nordic_ai_policy_tracker.schemas import (  # noqa: E402
    CoderType,
    CollectionStatus,
    DimensionScore,
)
from nordic_ai_policy_tracker.utils.logging import get_logger  # noqa: E402

logger = get_logger("calculate_indices")


def run_rule_based_coding(db_path: Path, coding_dimensions: dict) -> list[DimensionScore]:
    """Apply find_candidate_evidence + suggest_rule_based_score to every
    successfully-collected document, for every dimension, and persist the
    results as coder_type=RULE_BASED DimensionScore rows.
    """
    rows = [
        r
        for r in list_documents(db_path)
        if r["collection_status"] == CollectionStatus.COLLECTED.value
    ]
    all_scores: list[DimensionScore] = []
    now = datetime.now(UTC)

    for row in rows:
        cleaned_text = row["cleaned_text"] or ""
        for dim in coding_dimensions["dimensions"]:
            candidates = find_candidate_evidence(cleaned_text, dim["id"], dim["keyword_hints"])
            score_value = suggest_rule_based_score(candidates)
            plain_matches = [c for c in candidates if c.polarity == "plain_match"]
            evidence_passage = plain_matches[0].sentence if plain_matches else None

            if score_value == 0:
                # Per schema rules, a 0 score must not carry an evidence_passage
                # (evidence is required only for scores > 0).
                evidence_passage = None

            score = DimensionScore(
                document_id=row["document_id"],
                dimension_id=dim["id"],
                axis=dim["axis"],
                score=score_value,
                evidence_passage=evidence_passage,
                uncertainty_flag=bool(
                    candidates and all(c.polarity == "negative_or_hedged" for c in candidates)
                ),
                uncertainty_note=(
                    "All keyword matches for this dimension were flagged as negated/hedged; "
                    "rule-based score conservatively set to 0. A human coder should confirm."
                    if candidates and all(c.polarity == "negative_or_hedged" for c in candidates)
                    else None
                ),
                coder_id="rule_based_v1",
                coder_type=CoderType.RULE_BASED,
                coding_timestamp=now,
                coding_round=1,
            )
            save_dimension_score(db_path, score)
            all_scores.append(score)

    logger.info(
        "Stored %d rule-based dimension scores across %d documents.", len(all_scores), len(rows)
    )
    return all_scores


def compute_and_save_automated_hints(
    db_path: Path,
    documents_rows,
    scores: list[DimensionScore],
    coding_dimensions: dict,
) -> None:
    """Automated hints are always computed for every collected document --
    there is no completeness gate, since they're an exploratory aid, not a
    claim about the document. Lund is structurally excluded here because
    it never reaches collection_status == COLLECTED (its PDF collection
    failed -- see docs/limitations.md).
    """
    for row in documents_rows:
        if row["collection_status"] != CollectionStatus.COLLECTED.value:
            continue
        rei, pisi = compute_automated_hints_for_document(
            row["document_id"], scores, coding_dimensions
        )
        save_index_result(db_path, rei)
        save_index_result(db_path, pisi)
        logger.info(
            "%s: automated_rei_hint=%.1f (confidence=%.2f), automated_pisi_hint=%.1f "
            "(confidence=%.2f)",
            row["university_name"],
            rei.normalized_score,
            rei.confidence,
            pisi.normalized_score,
            pisi.confidence,
        )


def compute_and_save_human_and_validated(
    db_path: Path,
    documents_rows,
    scores: list[DimensionScore],
    coding_dimensions: dict,
) -> None:
    """Human/validated indices are only saved when their respective
    completeness gate is met (see modeling/indices.py docstrings). A
    document/axis with incomplete coding simply produces no row here --
    the dashboard shows "Not yet human-coded" for it, never a fabricated
    or partial number.
    """
    for row in documents_rows:
        if row["collection_status"] != CollectionStatus.COLLECTED.value:
            continue
        rei, pisi = compute_human_indices_for_document(
            row["document_id"], scores, coding_dimensions
        )
        for result, axis_label in ((rei, "human_rei"), (pisi, "human_pisi")):
            if result is None:
                logger.info(
                    "%s: %s -- not yet human-coded (axis incomplete).",
                    row["university_name"],
                    axis_label,
                )
                continue
            save_index_result(db_path, result)
            logger.info(
                "%s: %s=%.1f (confidence=%.2f)",
                row["university_name"],
                axis_label,
                result.normalized_score,
                result.confidence,
            )

        v_rei, v_pisi = compute_validated_indices_for_document(
            row["document_id"], scores, coding_dimensions
        )
        for result, axis_label in ((v_rei, "validated_rei"), (v_pisi, "validated_pisi")):
            if result is None:
                continue  # no round-2+ recoding yet -- expected for this pilot today
            save_index_result(db_path, result)
            logger.info(
                "%s: %s=%.1f (confidence=%.2f)",
                row["university_name"],
                axis_label,
                result.normalized_score,
                result.confidence,
            )


def load_human_scores_from_csv(csv_path: Path) -> list[DimensionScore]:
    """Parse a filled-in annotation CSV (same shape as
    data/annotations/annotation_template.csv) into DimensionScore objects.
    Rows with an empty `score` are skipped (not yet coded), not treated as 0.
    """
    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    scores: list[DimensionScore] = []
    for _, row in df.iterrows():
        if not row.get("score", "").strip():
            continue  # not yet coded -- skip, do not impute
        scores.append(
            DimensionScore(
                document_id=row["document_id"],
                dimension_id=row["dimension_id"],
                axis=row["axis"],
                score=int(row["score"]),
                evidence_passage=row["evidence_passage"] or None,
                evidence_start_offset=(
                    int(row["evidence_start_offset"]) if row["evidence_start_offset"] else None
                ),
                evidence_end_offset=(
                    int(row["evidence_end_offset"]) if row["evidence_end_offset"] else None
                ),
                uncertainty_flag=row["uncertainty_flag"].strip().lower() == "true",
                uncertainty_note=row["uncertainty_note"] or None,
                coder_id=row["coder_id"] or "unknown",
                coder_type=CoderType.HUMAN,
                coding_timestamp=(
                    datetime.fromisoformat(row["coding_timestamp"])
                    if row["coding_timestamp"]
                    else datetime.now(UTC)
                ),
                coding_round=int(row["coding_round"]) if row["coding_round"] else 1,
            )
        )
    return scores


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute rule-based (and optionally human) REI/PISI indices."
    )
    parser.add_argument(
        "--include-human", action="store_true", help="Also compute indices from human coding."
    )
    parser.add_argument(
        "--human-csv",
        type=str,
        default="data/annotations/annotation_template.csv",
        help="Path to a filled-in human annotation CSV.",
    )
    args = parser.parse_args()

    settings = get_settings()
    coding_dimensions = get_coding_dimensions()
    db_path = resolve_path(settings["paths"]["database_path"])

    scores = run_rule_based_coding(db_path, coding_dimensions)
    rows = list_documents(db_path)
    compute_and_save_automated_hints(db_path, rows, scores, coding_dimensions)

    if args.include_human:
        human_csv_path = resolve_path(args.human_csv)
        human_scores = load_human_scores_from_csv(human_csv_path)
        if not human_scores:
            logger.warning(
                "No human-coded rows found in %s (file is empty or all scores blank). "
                "Human coding has not been performed yet for this pilot -- see docs/coding_guide.md. "
                "No human_* or validated_* index rows will be written.",
                human_csv_path,
            )
        else:
            for score in human_scores:
                save_dimension_score(db_path, score)
            compute_and_save_human_and_validated(db_path, rows, human_scores, coding_dimensions)
    else:
        logger.info(
            "Human coding not requested (--include-human not set). Human coding for this pilot has not yet "
            "been performed -- see docs/coding_guide.md and the annotation template. No human_* or "
            "validated_* index rows will be written."
        )


if __name__ == "__main__":
    main()
