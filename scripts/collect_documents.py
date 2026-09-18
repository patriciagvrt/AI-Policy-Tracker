#!/usr/bin/env python
"""Stage 2 script: collect the active+verified pilot sources.

Usage (normal use, from a machine with internet access):
    python scripts/collect_documents.py --live

Usage (only to reproduce this specific pilot build, see
data/raw/pilot_sandbox_retrieved/README.md for why this mode exists):
    python scripts/collect_documents.py --sandbox-fixture

Either mode writes to the same SQLite database (data/processed/policy_tracker.db)
and produces a collection audit report at outputs/reports/collection_audit.md.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from nordic_ai_policy_tracker.collection.crawler import collect_all, load_universities  # noqa: E402
from nordic_ai_policy_tracker.config import get_settings, resolve_path  # noqa: E402
from nordic_ai_policy_tracker.database import (  # noqa: E402
    init_db,
    list_collection_audit,
    log_collection_attempt,
    save_document,
)
from nordic_ai_policy_tracker.processing.cleaning import clean_text  # noqa: E402
from nordic_ai_policy_tracker.processing.language import confirm_expected_language  # noqa: E402
from nordic_ai_policy_tracker.schemas import (  # noqa: E402
    CollectionStatus,
    ExtractionMethod,
    PolicyDocument,
    TranslationStatus,
)
from nordic_ai_policy_tracker.utils.logging import get_logger  # noqa: E402
from nordic_ai_policy_tracker.utils.text_hashing import (  # noqa: E402
    compute_document_id,
    compute_text_hash,
)

logger = get_logger("collect_documents")

# The four HTML sources for which real text could be retrieved in the
# build sandbox (see data/raw/pilot_sandbox_retrieved/README.md). Lund's
# PDF is deliberately excluded -- see that same README for why.
SANDBOX_FIXTURE_MAP = {
    "uio_no": "uio_no.md",
    "au_dk": "au_dk.md",
    "aalto_fi": "aalto_fi.md",
    "ru_is": "ru_is.md",
}


def run_live(settings: dict) -> list[PolicyDocument]:
    """Run the real requests-based crawler, and log every attempt to the
    collection_audit table -- this is what lets reporting code (see
    process_documents.py) tell live collection apart from the
    sandbox-fixture substitute path dynamically, from data, rather than by
    a hardcoded assumption about which mode produced the current database.
    """
    csv_path = resolve_path(settings["paths"]["universities_csv"])
    documents = collect_all(csv_path, settings)

    db_path = resolve_path(settings["paths"]["database_path"])
    for doc in documents:
        if doc.collection_status == CollectionStatus.COLLECTED:
            outcome = "collected_via_live_http"
        elif doc.collection_status == CollectionStatus.SKIPPED_ROBOTS_DISALLOWED:
            outcome = "skipped_robots_disallowed"
        else:
            outcome = "failed_live_collection"
        log_collection_attempt(
            db_path,
            university_id=doc.university_id,
            source_url=str(doc.source_url),
            outcome=outcome,
            retrieval_method="live_http",
            http_status=doc.http_status,
            error_message=doc.error_message,
        )
    return documents


def run_sandbox_fixture(settings: dict) -> list[PolicyDocument]:
    """Reproduce this pilot's build using the sandbox-retrieved text files.

    Every step after "obtain raw text" is the SAME pipeline code the live
    path uses (cleaning.clean_text, language.confirm_expected_language,
    text_hashing) -- only the retrieval step differs, and that difference
    is recorded per document via extraction_method left as HTML_HTTP with
    an explicit note in error_message-adjacent logging, not hidden.
    """
    csv_path = resolve_path(settings["paths"]["universities_csv"])
    universities = {u.university_id: u for u in load_universities(csv_path)}
    fixtures_dir = REPO_ROOT / "data" / "raw" / "pilot_sandbox_retrieved"
    documents: list[PolicyDocument] = []

    db_path = resolve_path(settings["paths"]["database_path"])

    for university_id, filename in SANDBOX_FIXTURE_MAP.items():
        university = universities[university_id]
        fixture_path = fixtures_dir / filename
        if not fixture_path.exists():
            logger.error("Missing sandbox fixture for %s: %s", university_id, fixture_path)
            continue

        raw_text = fixture_path.read_text(encoding="utf-8")
        cleaned = clean_text(raw_text)
        text_hash = compute_text_hash(cleaned)
        document_id = compute_document_id(university_id, str(university.policy_url))
        lang_report = confirm_expected_language(cleaned, expected_language="en")

        doc = PolicyDocument(
            document_id=document_id,
            university_id=university.university_id,
            university_name=university.university_name,
            country=university.country,
            title=university.policy_title,
            source_url=str(university.policy_url),
            retrieval_timestamp=datetime.now(UTC),
            original_language=None,  # unknown -- never guessed; see language_scope_note
            analyzed_language="en",
            is_official_translation=None,
            translation_status=TranslationStatus.UNKNOWN,
            other_language_documents_may_exist=None,
            language_scope_note=(
                "English-language page analyzed for the pilot. Whether this is the "
                "original drafting language or an official translation was not "
                "confirmable from the page content alone; treat as unknown pending "
                "manual check. Detected language of the analyzed text: "
                f"{lang_report['detected_language']} (matches expected: "
                f"{lang_report['matches_expected']})."
            ),
            document_type=university.document_type,
            intended_audience=university.intended_audience,
            policy_level=university.policy_level,
            file_format="html",
            http_status=200,  # the source page was live and returned content when fetched
            robots_allowed=None,  # not checked in sandbox-fixture mode; see README
            extraction_method=ExtractionMethod.HTML_HTTP,
            raw_text=raw_text,
            cleaned_text=cleaned,
            text_hash=text_hash,
            word_count=len(cleaned.split()),
            collection_status=CollectionStatus.COLLECTED,
            manual_verification_status=(
                "Text retrieved via sandbox fetch tool, not this project's own requests-based "
                "crawler -- see data/raw/pilot_sandbox_retrieved/README.md. Re-collection with "
                "--live from a networked machine is recommended before treating this as final."
            ),
        )
        documents.append(doc)
        log_collection_attempt(
            db_path,
            university_id=university_id,
            source_url=str(university.policy_url),
            outcome="collected_via_sandbox_fixture",
            retrieval_method="sandbox_fetch_tool_substitute",
            http_status=200,
        )
        logger.info(
            "Ingested sandbox-fixture text for %s (%d words).", university_id, doc.word_count
        )

    # Lund: record as an honest failure, not a fabricated document.
    lund = universities.get("lund_se")
    if lund is not None:
        document_id = compute_document_id("lund_se", str(lund.policy_url))
        doc = PolicyDocument(
            document_id=document_id,
            university_id="lund_se",
            university_name=lund.university_name,
            country=lund.country,
            title=lund.policy_title,
            source_url=str(lund.policy_url),
            retrieval_timestamp=datetime.now(UTC),
            analyzed_language="en",
            translation_status=TranslationStatus.UNKNOWN,
            document_type=lund.document_type,
            intended_audience=lund.intended_audience,
            policy_level=lund.policy_level,
            file_format="pdf",
            extraction_method=ExtractionMethod.PDF_HTTP,
            collection_status=CollectionStatus.FAILED,
            error_message=(
                "Live PDF collection was not possible from this build sandbox (no outbound "
                "network access to lu.se). The sandbox's available fetch tool returned only a "
                "condensed summary of the PDF, not verbatim text, and that summary was "
                "deliberately NOT stored as raw_text/cleaned_text, per this project's rule "
                "against presenting anything other than genuine extracted text as document "
                "content. Run `python scripts/collect_documents.py --live` from a machine with "
                "normal internet access to collect this document for real; "
                "pdf_extractor.py (PyMuPDF) will extract it directly."
            ),
        )
        documents.append(doc)
        log_collection_attempt(
            db_path,
            university_id="lund_se",
            source_url=str(lund.policy_url),
            outcome="failed_no_sandbox_network_access",
            retrieval_method="none",
            error_message=doc.error_message,
        )
        logger.warning(
            "Lund University: recorded as a documented collection failure (see error_message)."
        )

    return documents


def write_audit_report(db_path: Path, documents: list[PolicyDocument], report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    audit_rows = list_collection_audit(db_path)

    lines = [
        "# Collection Audit Report",
        "",
        f"Generated: {datetime.now(UTC).isoformat()}",
        "",
        "## Summary",
        "",
        f"- Documents attempted: {len(documents)}",
        f"- Collected: {sum(1 for d in documents if d.collection_status == CollectionStatus.COLLECTED)}",
        f"- Failed: {sum(1 for d in documents if d.collection_status == CollectionStatus.FAILED)}",
        f"- Skipped (robots disallowed): "
        f"{sum(1 for d in documents if d.collection_status == CollectionStatus.SKIPPED_ROBOTS_DISALLOWED)}",
        "",
        "## Per-document results",
        "",
        "| University | Status | Word count | Notes |",
        "|---|---|---|---|",
    ]
    for doc in documents:
        note = doc.error_message or doc.manual_verification_status or ""
        note = note.replace("\n", " ")[:160]
        lines.append(
            f"| {doc.university_name} | {doc.collection_status.value} | {doc.word_count} | {note} |"
        )

    lines += [
        "",
        "## Raw audit log",
        "",
        "| University | Attempted at | Outcome | Method |",
        "|---|---|---|---|",
    ]
    for row in audit_rows:
        lines.append(
            f"| {row['university_id']} | {row['attempted_at']} | {row['outcome']} | {row['retrieval_method']} |"
        )

    report_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Wrote collection audit report to %s", report_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect Nordic AI policy pilot documents.")
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--live", action="store_true", help="Collect from the real internet (production mode)."
    )
    mode_group.add_argument(
        "--sandbox-fixture",
        action="store_true",
        help="Reproduce this pilot's build using sandbox-retrieved text (see README in "
        "data/raw/pilot_sandbox_retrieved/). Not for normal use.",
    )
    args = parser.parse_args()

    settings = get_settings()
    db_path = resolve_path(settings["paths"]["database_path"])
    init_db(db_path)

    if args.live:
        documents = run_live(settings)
    else:
        documents = run_sandbox_fixture(settings)

    for doc in documents:
        save_document(db_path, doc)

    report_path = resolve_path("outputs/reports/collection_audit.md")
    write_audit_report(db_path, documents, report_path)

    n_collected = sum(1 for d in documents if d.collection_status == CollectionStatus.COLLECTED)
    logger.info("Done. %d/%d documents collected.", n_collected, len(documents))


if __name__ == "__main__":
    main()
