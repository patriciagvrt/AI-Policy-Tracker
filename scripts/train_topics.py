#!/usr/bin/env python
"""Stage 5 script: exploratory BERTopic modeling over the pilot's chunks.

Reads data/processed/chunks.parquet (produced by process_documents.py),
fits a topic model (or refuses to, gracefully, if there isn't enough data
-- see modeling/bertopic_pipeline.py), and writes:
  - data/processed/topic_assignments.parquet (chunk -> topic mapping)
  - data/processed/topic_labels.parquet (automatic + manual labels, kept
    separate -- see schemas.TopicLabel)
  - outputs/reports/topic_model_report.md (human-readable summary,
    including the keyword-vectorizer configuration and the
    institution/document-type diagnostics)

This pilot has only a handful of successfully collected documents and a
relatively small number of chunks. The pipeline's own
min_documents_for_modeling threshold (config/settings.yaml) is met, so a
model WILL be attempted -- but its output must be read as
experimental/exploratory, not as stable or generalizable topics. That
caveat is written directly into the output report, not left to the reader
to infer.

Usage:
    python scripts/train_topics.py
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

import pandas as pd  # noqa: E402

from nordic_ai_policy_tracker.config import get_settings, resolve_path  # noqa: E402
from nordic_ai_policy_tracker.database import list_documents  # noqa: E402
from nordic_ai_policy_tracker.modeling.bertopic_pipeline import (  # noqa: E402
    InsufficientDataError,
    run_topic_model,
)
from nordic_ai_policy_tracker.modeling.topic_diagnostics import (  # noqa: E402
    INSTITUTION_DOMINANCE_THRESHOLD,
    compute_institution_dominance,
    compute_topic_document_type_table,
    compute_topic_university_table,
)
from nordic_ai_policy_tracker.schemas import (  # noqa: E402
    ManualLabelStatus,
    TopicChunk,
    TopicLabel,
)
from nordic_ai_policy_tracker.utils.logging import get_logger  # noqa: E402

logger = get_logger("train_topics")

# Provisional researcher interpretations of the current 3-topic model,
# supplied by the project owner after reviewing the automatic (c-TF-IDF)
# keywords. These are stored SEPARATELY from each topic's
# automatic_topic_label (see schemas.TopicLabel / schemas.ManualLabelStatus)
# and are explicitly marked `provisional` -- not `confirmed` -- because they
# have not yet been re-checked against the improved (stopword-filtered,
# n-gram-aware) keyword output. If a future run's automatic keywords for a
# given topic_id no longer resemble what motivated this label, the
# provisional label should be re-reviewed, not assumed to still apply.
PROVISIONAL_MANUAL_LABELS: dict[int, str] = {
    0: "Responsible and safe AI use",
    1: "Institutional support and AI literacy",
    2: "Assessment rules and AI disclosure",
}
PROVISIONAL_MANUAL_LABEL_NOTE = (
    "Provisional researcher interpretation, not yet confirmed. Proposed after reviewing "
    "this topic's automatic (c-TF-IDF) keywords; requires researcher confirmation before "
    "being treated as settled."
)


def _document_rows_for_chunks(db_path: Path) -> list:
    """documents-table rows, used only for their document_id -> (university,
    document_type) metadata by the diagnostics module. Read-only; this
    script never writes to the documents table.
    """
    return list_documents(db_path)


def main() -> None:
    settings = get_settings()
    processed_dir = resolve_path(settings["paths"]["processed_dir"])
    chunks_path = processed_dir / "chunks.parquet"
    report_path = resolve_path("outputs/reports/topic_model_report.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)

    if not chunks_path.exists():
        logger.error(
            "No chunks.parquet found at %s. Run scripts/process_documents.py first.", chunks_path
        )
        report_path.write_text(
            "# Topic Model Report\n\nNo chunks were available (process_documents.py has not been run, "
            "or produced zero chunks). Topic modeling was not attempted.\n",
            encoding="utf-8",
        )
        return

    chunks_df = pd.read_parquet(chunks_path)
    chunks = [
        TopicChunk(
            chunk_id=row["chunk_id"],
            document_id=row["document_id"],
            university_id=row["university_id"],
            chunk_index=int(row["chunk_index"]),
            chunk_text=row["chunk_text"],
        )
        for _, row in chunks_df.iterrows()
    ]

    bertopic_cfg = settings["bertopic"]
    try:
        result = run_topic_model(
            chunks,
            embedding_model_name=bertopic_cfg["embedding_model"],
            random_seed=bertopic_cfg["random_seed"],
            min_topic_size=bertopic_cfg["min_topic_size"],
            min_documents_for_modeling=bertopic_cfg["min_documents_for_modeling"],
        )
    except InsufficientDataError as exc:
        logger.warning("Topic modeling refused: %s", exc)
        report_path.write_text(
            "# Topic Model Report\n\n"
            "**Topic modeling was NOT run.** The pipeline refused to fabricate a model:\n\n"
            f"> {exc}\n\n"
            "This is expected behavior for a small pilot corpus and is not a bug -- see "
            "docs/limitations.md (BERTopic small-corpus limitation).\n",
            encoding="utf-8",
        )
        return
    except (
        Exception
    ) as exc:  # noqa: BLE001 -- deliberately broad: report honestly, never fabricate output
        logger.error("Topic modeling failed to run: %s", exc)
        report_path.write_text(
            "# Topic Model Report\n\n"
            "**Topic modeling was NOT run** because an error occurred while fitting the model "
            "(not because of insufficient data -- the corpus met the minimum document/chunk "
            "thresholds). This is reported honestly here rather than showing fabricated topics.\n\n"
            f"Error: `{type(exc).__name__}: {exc}`\n\n"
            "The most common cause in this project's build sandbox is that downloading the "
            "sentence-transformers embedding model requires reaching huggingface.co, which is "
            "outside this sandbox's network allowlist (confirmed separately: a direct request to "
            "huggingface.co is rejected by the sandbox's egress policy with a 403). "
            "`src/nordic_ai_policy_tracker/modeling/bertopic_pipeline.py` itself has no dependency "
            "on this sandbox and will run normally on a machine with regular internet access -- run "
            "`python scripts/train_topics.py` there to get real topic output. See "
            "docs/limitations.md.\n",
            encoding="utf-8",
        )
        return

    # --- Persist chunk -> topic assignments. ---
    assignments_rows = [
        {
            "chunk_id": c.chunk_id,
            "document_id": c.document_id,
            "university_id": c.university_id,
            "chunk_index": c.chunk_index,
            "topic_id": c.topic_id,
            "topic_probability": c.topic_probability,
            "is_outlier": c.is_outlier,
        }
        for c in result.topic_chunks
    ]
    assignments_df = pd.DataFrame(assignments_rows)
    assignments_path = processed_dir / "topic_assignments.parquet"
    assignments_df.to_parquet(assignments_path, index=False)
    logger.info("Wrote topic assignments to %s", assignments_path)

    n_outliers = sum(1 for c in result.topic_chunks if c.is_outlier)
    topic_ids = sorted({c.topic_id for c in result.topic_chunks if not c.is_outlier})
    n_topics = len(topic_ids)

    # --- Automatic + manual topic labels, kept as separate fields. ---
    topic_sizes = {
        topic_row.get("Topic"): topic_row.get("Count")
        for topic_row in result.topic_info
        if topic_row.get("Topic") != -1
    }
    topic_labels: list[TopicLabel] = []
    for topic_id in topic_ids:
        keywords = result.topic_keywords.get(topic_id, [])
        automatic_label = "_".join(keywords[:4]) if keywords else f"topic_{topic_id}"
        manual_label = PROVISIONAL_MANUAL_LABELS.get(topic_id)
        topic_labels.append(
            TopicLabel(
                topic_id=topic_id,
                automatic_topic_label=automatic_label,
                top_keywords=keywords,
                chunk_count=int(topic_sizes.get(topic_id, 0) or 0),
                manual_topic_label=manual_label,
                manual_label_status=(
                    ManualLabelStatus.PROVISIONAL
                    if manual_label is not None
                    else ManualLabelStatus.UNLABELED
                ),
                manual_label_note=(PROVISIONAL_MANUAL_LABEL_NOTE if manual_label else None),
            )
        )
    topic_labels_df = pd.DataFrame([label.model_dump() for label in topic_labels])
    topic_labels_path = processed_dir / "topic_labels.parquet"
    if not topic_labels_df.empty:
        topic_labels_df.to_parquet(topic_labels_path, index=False)
        logger.info("Wrote topic labels to %s", topic_labels_path)

    # --- Institution / document-type diagnostics. ---
    db_path = resolve_path(settings["paths"]["database_path"])
    document_rows = _document_rows_for_chunks(db_path)
    university_table = compute_topic_university_table(result.topic_chunks, document_rows)
    dominance_summary = compute_institution_dominance(result.topic_chunks, document_rows)
    doc_type_table = compute_topic_document_type_table(result.topic_chunks, document_rows)

    used_fallback = result.parameters.get("topic_method") == "tfidf_fallback"

    lines = [
        "# Topic Model Report (EXPERIMENTAL — pilot corpus)",
        "",
        f"Generated: {datetime.now(UTC).isoformat()}",
        "",
        "> **This output is exploratory only.** It was fit on "
        f"{result.parameters['n_documents']} document(s) and "
        f"{result.parameters['n_chunks']} chunk(s) -- far too few for the "
        "resulting topics to be considered stable, representative, or "
        "nationally generalizable. Do not use these topic assignments as "
        "evidence for REI/PISI scores; those are computed independently and "
        "entirely separately (see modeling/indices.py) and are never "
        "connected to BERTopic topic probabilities. See docs/limitations.md.",
        "",
    ]

    if used_fallback:
        lines += [
            "> **`topic_method=tfidf_fallback`, `topic_status=experimental`, "
            "`semantic_embeddings_used=false`.** The configured sentence-transformer "
            "embedding model (`" + str(result.parameters.get("embedding_model_requested")) + "`) "
            "could not be downloaded in this project's build sandbox, which has no network path "
            "to huggingface.co. A local TF-IDF embedding (scikit-learn) was used instead, purely "
            "to test that the pipeline runs end to end. **This is NOT the final BERTopic "
            "analysis.** Re-run `python scripts/train_topics.py` on a machine with network access "
            "to huggingface.co so the configured sentence-transformer model can actually be used, "
            "before treating these topics as anything more than a pipeline smoke test. Even with "
            "real semantic embeddings, this pilot's corpus is too small for the resulting topics "
            "to be generalizable -- see docs/limitations.md.",
            "",
        ]

    lines += [
        "## Parameters used",
        "",
        "| Parameter | Value |",
        "|---|---|",
    ]
    for key, value in result.parameters.items():
        if key == "keyword_vectorizer":
            continue  # rendered as its own subsection below, not squeezed into this table
        lines.append(f"| {key} | {value} |")

    vec_cfg = result.parameters.get("keyword_vectorizer", {})
    lines += [
        "",
        "### Keyword vectorizer (c-TF-IDF label/keyword extraction)",
        "",
        "This is the vectorizer BERTopic uses to pick each topic's keywords and label -- a "
        "separate concern from the embedding model above, which only affects clustering. See "
        "`build_keyword_vectorizer()` in `modeling/bertopic_pipeline.py` for the full rationale.",
        "",
        "| Setting | Value |",
        "|---|---|",
    ]
    for key, value in vec_cfg.items():
        lines.append(f"| {key} | {value} |")
    if vec_cfg.get("min_df_fallback_applied"):
        lines += [
            "",
            f"> **min_df fallback applied:** {vec_cfg.get('min_df_fallback_reason')}",
        ]

    lines += [
        "",
        f"## Summary: {n_topics} topic(s) found, {n_outliers} outlier chunk(s) "
        f"out of {len(result.topic_chunks)} total chunks",
        "",
        "## Topics",
        "",
        "Each topic below shows its **automatic** label (BERTopic's own c-TF-IDF keywords) and, "
        "where one has been proposed, a **provisional manual label** -- a researcher's "
        "interpretation, always marked `provisional` until explicitly confirmed, and never "
        "presented as if the model produced it.",
        "",
    ]
    label_by_topic = {label.topic_id: label for label in topic_labels}
    for topic_row in result.topic_info:
        topic_id = topic_row.get("Topic")
        if topic_id == -1:
            lines.append(f"### Outliers (Topic -1): {topic_row.get('Count')} chunk(s)")
            continue
        label = label_by_topic.get(topic_id)
        lines.append(f"### Topic {topic_id} ({topic_row.get('Count')} chunk(s))")
        lines.append("")
        if label is not None:
            lines.append(
                f"- **Automatic label** (c-TF-IDF keywords): `{label.automatic_topic_label}`"
            )
            lines.append(f"- **Top keywords**: {', '.join(label.top_keywords) or '(none)'}")
            if label.manual_topic_label:
                lines.append(
                    f"- **Manual label** (`{label.manual_label_status.value}`): "
                    f'"{label.manual_topic_label}" -- {label.manual_label_note}'
                )
            else:
                lines.append("- **Manual label**: none proposed yet (`unlabeled`)")
        reps = result.representative_docs.get(int(topic_id), [])
        for rep in reps:
            snippet = rep[:300].replace("\n", " ")
            lines.append(
                f'- Representative passage: "{snippet}..."'
                if len(rep) > 300
                else f'- Representative passage: "{snippet}"'
            )
        lines.append("")

    # --- Institution-dominance diagnostics ---
    lines += [
        "## Institution-dominance diagnostics",
        "",
        "An institution-dominated topic (most of its chunks from one university) may reflect "
        "that source's writing style, document type, or source-specific vocabulary rather than "
        "a general policy theme shared across the corpus. This is flagged here so a topic is "
        "never read as a cross-institution theme without checking this table first. Flag "
        f"threshold: a topic where the dominant university accounts for more than "
        f"{int(INSTITUTION_DOMINANCE_THRESHOLD * 100)}% of its chunks.",
        "",
        "| Topic | Total chunks | Dominant university | Dominant share | # universities | Entropy | Flag |",
        "|---|---|---|---|---|---|---|",
    ]
    if dominance_summary:
        for row in dominance_summary:
            flag = "⚠️ institution-specific" if row["institution_dominance_flag"] else ""
            lines.append(
                f"| {row['topic_id']} | {row['total_chunks']} | {row['dominant_university_name']} | "
                f"{row['dominant_university_share']}% | {row['n_universities']} | {row['entropy']} | "
                f"{flag} |"
            )
    else:
        lines.append("| (no non-outlier topics) | | | | | | |")

    lines += [
        "",
        "### Topic-by-university breakdown",
        "",
        "| Topic | University | Chunks | % of topic | % of university's chunks |",
        "|---|---|---|---|---|",
    ]
    if university_table:
        for row in university_table:
            lines.append(
                f"| {row['topic_id']} | {row['university_name']} | {row['chunk_count']} | "
                f"{row['pct_of_topic']}% | {row['pct_of_university']}% |"
            )
    else:
        lines.append("| (no non-outlier topics) | | | | |")

    # --- Document-type diagnostics ---
    lines += [
        "",
        "## Document-type diagnostics",
        "",
        "Document type (institution-wide policy / student guidance / examination guidance / "
        "teaching-and-learning guidance) may explain a topic's content better than country or "
        "university does -- shown here for the same reason as the university breakdown above.",
        "",
        "| Topic | Document type | Chunks | % of topic |",
        "|---|---|---|---|",
    ]
    if doc_type_table:
        for row in doc_type_table:
            lines.append(
                f"| {row['topic_id']} | {row['document_type']} | {row['chunk_count']} | "
                f"{row['pct_of_topic']}% |"
            )
    else:
        lines.append("| (no non-outlier topics) | | | |")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Wrote topic model report to %s", report_path)


if __name__ == "__main__":
    main()
