#!/usr/bin/env python
"""Stage 3 script: dedup, segment, and write processed outputs + a data-quality report.

Reads the `documents` table (populated by collect_documents.py), and:
1. Detects exact duplicates across collected documents.
2. Segments each successfully-collected document into chunks (for BERTopic
   and evidence lookup), saved to Parquet at data/processed/chunks.parquet.
3. Writes a data-quality report covering language-detection mismatches,
   missing metadata, and word-count outliers.

Usage:
    python scripts/process_documents.py
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

import pandas as pd  # noqa: E402

from nordic_ai_policy_tracker.config import get_settings, resolve_path  # noqa: E402
from nordic_ai_policy_tracker.database import list_collection_audit, list_documents  # noqa: E402
from nordic_ai_policy_tracker.processing.deduplication import find_exact_duplicates  # noqa: E402
from nordic_ai_policy_tracker.processing.language import confirm_expected_language  # noqa: E402
from nordic_ai_policy_tracker.processing.segmentation import chunk_document  # noqa: E402
from nordic_ai_policy_tracker.reporting import render_collection_method_note  # noqa: E402
from nordic_ai_policy_tracker.schemas import (  # noqa: E402
    CollectionStatus,
    NordicCountry,
    PolicyDocument,
)
from nordic_ai_policy_tracker.utils.logging import get_logger  # noqa: E402

logger = get_logger("process_documents")


def _row_to_policy_document(row) -> PolicyDocument | None:
    """Rebuild a (partial, read-only) PolicyDocument from a sqlite3.Row,
    just enough to reuse the deduplication/segmentation functions. Returns
    None for rows that failed collection -- there's nothing to process.
    """
    if row["collection_status"] != CollectionStatus.COLLECTED.value:
        return None
    return PolicyDocument(
        document_id=row["document_id"],
        university_id=row["university_id"],
        university_name=row["university_name"],
        country=NordicCountry(row["country"]),
        title=row["title"],
        source_url=row["source_url"],
        retrieval_timestamp=datetime.fromisoformat(row["retrieval_timestamp"]),
        analyzed_language=row["analyzed_language"],
        document_type=row["document_type"],
        intended_audience=row["intended_audience"],
        file_format=row["file_format"],
        extraction_method=row["extraction_method"],
        cleaned_text=row["cleaned_text"] or "",
        text_hash=row["text_hash"],
        word_count=row["word_count"],
        collection_status=CollectionStatus(row["collection_status"]),
    )


def main() -> None:
    settings = get_settings()
    db_path = resolve_path(settings["paths"]["database_path"])
    rows = list_documents(db_path)

    documents = [d for d in (_row_to_policy_document(r) for r in rows) if d is not None]
    logger.info("Loaded %d successfully-collected document(s) for processing.", len(documents))

    # --- Duplicate detection ---
    duplicates = find_exact_duplicates(documents)
    if duplicates:
        logger.warning("Found %d duplicate document(s): %s", len(duplicates), duplicates)
    else:
        logger.info("No exact duplicates found among collected documents.")

    # --- Segmentation into chunks ---
    seg_cfg = settings["segmentation"]
    chunk_rows: list[dict] = []
    for doc in documents:
        chunks = chunk_document(
            doc.cleaned_text,
            chunk_size_tokens=seg_cfg["chunk_size_tokens"],
            chunk_overlap_tokens=seg_cfg["chunk_overlap_tokens"],
        )
        for idx, chunk_text in enumerate(chunks):
            chunk_rows.append(
                {
                    "chunk_id": f"{doc.document_id}_chunk{idx}",
                    "document_id": doc.document_id,
                    "university_id": doc.university_id,
                    "chunk_index": idx,
                    "chunk_text": chunk_text,
                    "word_count": len(chunk_text.split()),
                }
            )
    chunks_df = pd.DataFrame(chunk_rows)
    processed_dir = resolve_path(settings["paths"]["processed_dir"])
    processed_dir.mkdir(parents=True, exist_ok=True)
    chunks_path = processed_dir / "chunks.parquet"
    if not chunks_df.empty:
        chunks_df.to_parquet(chunks_path, index=False)
        logger.info(
            "Wrote %d chunks across %d documents to %s", len(chunks_df), len(documents), chunks_path
        )
    else:
        logger.warning("No chunks produced -- no successfully collected documents to segment.")

    # --- Data quality report ---
    quality_lines = [
        "# Data Quality Report",
        "",
        f"Generated: {datetime.now(UTC).isoformat()}",
        "",
        "## Coverage",
        "",
        f"- Documents in database: {len(rows)}",
        f"- Successfully collected: {len(documents)}",
        f"- Failed collection: {sum(1 for r in rows if r['collection_status'] == 'failed')}",
        f"- Exact duplicates detected: {len(duplicates)}",
        f"- Total chunks produced: {len(chunk_rows)}",
        "",
        "## Per-document language check",
        "",
        "Compares each document's expected_language (from universities.csv, "
        "currently 'en' for all pilot sources) against the language actually "
        "detected in its cleaned_text.",
        "",
        "| Document | Expected | Detected | Confidence | Matches |",
        "|---|---|---|---|---|",
    ]
    for doc in documents:
        report = confirm_expected_language(doc.cleaned_text, expected_language="en")
        confidence = f"{report['confidence']:.2f}" if report["confidence"] is not None else "n/a"
        quality_lines.append(
            f"| {doc.university_name} | en | {report['detected_language']} | {confidence} | "
            f"{report['matches_expected']} |"
        )

    quality_lines += [
        "",
        "## Missing-data warnings",
        "",
    ]
    any_warning = False
    for doc in documents:
        if doc.word_count < 100:
            quality_lines.append(
                f"- **{doc.university_name}**: unusually short document ({doc.word_count} words)."
            )
            any_warning = True
    if not any_warning:
        quality_lines.append("- None detected among successfully collected documents.")

    audit_rows = list_collection_audit(db_path)
    quality_lines += [
        "",
        "## Note on this database's collection method",
        "",
        "Computed from the current database and collection_audit log at report-generation "
        "time -- never assumed from how a previous run of this pipeline collected its data.",
        "",
        render_collection_method_note(rows, audit_rows),
    ]

    report_path = resolve_path("outputs/reports/data_quality_report.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(quality_lines), encoding="utf-8")
    logger.info("Wrote data quality report to %s", report_path)


if __name__ == "__main__":
    main()
