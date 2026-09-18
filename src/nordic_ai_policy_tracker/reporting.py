"""Shared helpers for turning raw pipeline state (documents +
collection_audit rows) into report prose, so a report never has to
hardcode an assumption about *how* the data underneath it was collected.

Why this exists: an earlier version of scripts/process_documents.py
hardcoded a sentence describing this pilot's original sandbox-restricted
build ("Four of five documents were retrieved via a sandbox-specific
fallback... Lund University's PDF could not be collected..."). That
sentence was true when it was written, but it does not update itself --
once a user runs `python scripts/collect_documents.py --live` on a
machine with normal internet access and collects all five documents for
real, the hardcoded sentence becomes false while the code keeps printing
it anyway. The functions here replace that hardcoded sentence with one
computed from the current database and collection_audit log every time a
report is generated, so the report can never describe a database state
other than the one it was actually generated from.
"""

from __future__ import annotations

# Human-readable collection-method labels, keyed by a normalized signal
# from either the collection_audit.retrieval_method column or (as a
# fallback, for older rows / manually-imported documents that never went
# through log_collection_attempt) the documents.manual_verification_status
# free-text field.
LIVE_HTTP = "live HTTP collection"
SANDBOX_FIXTURE = "sandbox fixture collection"
MANUAL_IMPORT = "manual import"
FAILED = "failed collection"
UNKNOWN = "collection method not recorded"

_RETRIEVAL_METHOD_LABELS = {
    "live_http": LIVE_HTTP,
    "sandbox_fetch_tool_substitute": SANDBOX_FIXTURE,
    "manual_import": MANUAL_IMPORT,
    "none": FAILED,
}


def _label_from_retrieval_method(retrieval_method: str | None) -> str | None:
    if not retrieval_method:
        return None
    return _RETRIEVAL_METHOD_LABELS.get(retrieval_method)


def _label_from_manual_verification_status(manual_verification_status: str | None) -> str | None:
    """Fallback for documents with no matching collection_audit row (e.g.
    collected before live-path audit logging existed, or a document a
    researcher added to the database by hand rather than through either
    collection path). Looks for this project's own known phrasings rather
    than guessing.
    """
    if not manual_verification_status:
        return None
    text = manual_verification_status.lower()
    if "sandbox fetch tool" in text or "sandbox-fetch" in text:
        return SANDBOX_FIXTURE
    if "manual import" in text or "manually imported" in text:
        return MANUAL_IMPORT
    return None


def classify_collection_method(
    document_row,
    audit_rows_by_university: dict[str, list[dict]],
) -> str:
    """Determine how one document's row was actually collected, using only
    data already in the database -- never a hardcoded assumption about
    which mode produced the current database.

    Args:
        document_row: a documents-table row (sqlite3.Row or dict-like) with
            at least `collection_status`, `university_id`, and
            `manual_verification_status`.
        audit_rows_by_university: collection_audit rows grouped by
            `university_id`, most-recent attempt last (as
            list_collection_audit's ORDER BY attempted_at DESC would need
            reversing, or however the caller has grouped them -- this
            function reads the LAST entry in each list as the most recent
            attempt for that university).

    Returns:
        One of LIVE_HTTP, SANDBOX_FIXTURE, MANUAL_IMPORT, FAILED, or
        UNKNOWN.
    """
    collection_status = document_row["collection_status"]
    if collection_status == "failed":
        return FAILED

    university_id = document_row["university_id"]
    audit_rows = audit_rows_by_university.get(university_id, [])
    if audit_rows:
        # Most recent attempt for this university wins -- a document that
        # was first tried via one method and later re-collected via
        # another should be described by how it actually ended up in the
        # database now, not by its first-ever attempt.
        most_recent = audit_rows[-1]
        label = _label_from_retrieval_method(most_recent.get("retrieval_method"))
        if label is not None:
            return label

    fallback_label = _label_from_manual_verification_status(
        document_row["manual_verification_status"]
        if "manual_verification_status" in document_row.keys()
        else None
    )
    if fallback_label is not None:
        return fallback_label

    if collection_status == "collected":
        # Collected, with no collection_audit row and no recognizable
        # manual-verification note. This is NOT treated as unknown: the
        # sandbox-fixture path (run_sandbox_fixture in
        # scripts/collect_documents.py) always leaves an explicit
        # manual_verification_status marker on every document it
        # produces, and manual imports are expected to be noted the same
        # way. A collected document with neither marker -- including one
        # collected before this module's collection_audit logging existed
        # -- is therefore live HTTP collection by elimination, not a
        # guess: it is the only collection path that does not tag its own
        # output, so absence of a tag IS the signal.
        return LIVE_HTTP
    return UNKNOWN


def summarize_collection_methods(
    document_rows: list,
    audit_rows: list,
) -> dict[str, int]:
    """Groups a set of document rows by collection method and counts them.

    Never hardcodes a document count, a university name, or a date --
    every number in the result is computed from document_rows/audit_rows
    as given.
    """
    audit_by_university: dict[str, list[dict]] = {}
    for row in audit_rows:
        audit_by_university.setdefault(row["university_id"], []).append(dict(row))

    counts: dict[str, int] = {}
    for row in document_rows:
        label = classify_collection_method(row, audit_by_university)
        counts[label] = counts.get(label, 0) + 1
    return counts


def render_collection_method_note(document_rows: list, audit_rows: list) -> str:
    """Renders the "how was this database's data actually collected"
    paragraph(s) for a report, entirely from the given rows. This is the
    direct replacement for the old hardcoded sentence in
    scripts/process_documents.py.
    """
    counts = summarize_collection_methods(document_rows, audit_rows)
    total = sum(counts.values())
    if total == 0:
        return "No documents are recorded in the database yet."

    lines = []
    if len(counts) == 1:
        only_label, only_count = next(iter(counts.items()))
        if only_label == LIVE_HTTP:
            lines.append(
                f"All {only_count} document(s) in this database were collected through the "
                "live collection pipeline (`python scripts/collect_documents.py --live`)."
            )
        elif only_label == FAILED:
            lines.append(
                f"All {only_count} document(s) in this database currently have a failed "
                "collection status -- no successfully collected document exists yet."
            )
        else:
            lines.append(
                f"All {only_count} document(s) in this database were collected via {only_label}."
            )
    else:
        lines.append("This database's documents were collected through more than one method:")
        lines.append("")
        for label, count in sorted(counts.items(), key=lambda kv: kv[0]):
            lines.append(f"- {label}: {count} document(s)")

    return "\n".join(lines)
