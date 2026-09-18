"""Tests for nordic_ai_policy_tracker.reporting: the dynamic
collection-method classification that replaced a previously hardcoded
report sentence about sandbox-fixture collection and Lund's failure.

These tests exist specifically to prevent that stale sentence from ever
reappearing: they prove the report text is derived from the given rows,
so it changes when the underlying data changes, rather than being fixed
prose baked into the report-writing code.
"""

from __future__ import annotations

from nordic_ai_policy_tracker.reporting import (
    FAILED,
    LIVE_HTTP,
    SANDBOX_FIXTURE,
    classify_collection_method,
    render_collection_method_note,
    summarize_collection_methods,
)


def _doc_row(university_id, collection_status, manual_verification_status=None):
    return {
        "university_id": university_id,
        "collection_status": collection_status,
        "manual_verification_status": manual_verification_status,
    }


def _audit_row(university_id, retrieval_method, outcome="collected"):
    return {
        "university_id": university_id,
        "retrieval_method": retrieval_method,
        "outcome": outcome,
    }


def test_classify_collection_method_live_http_from_audit_log():
    doc = _doc_row("uio_no", "collected")
    audit = {"uio_no": [dict(_audit_row("uio_no", "live_http"))]}
    assert classify_collection_method(doc, audit) == LIVE_HTTP


def test_classify_collection_method_sandbox_fixture_from_audit_log():
    doc = _doc_row("au_dk", "collected")
    audit = {"au_dk": [dict(_audit_row("au_dk", "sandbox_fetch_tool_substitute"))]}
    assert classify_collection_method(doc, audit) == SANDBOX_FIXTURE


def test_classify_collection_method_failed_regardless_of_audit_log():
    doc = _doc_row("lund_se", "failed")
    audit = {"lund_se": [dict(_audit_row("lund_se", "none", outcome="failed"))]}
    assert classify_collection_method(doc, audit) == FAILED


def test_classify_collection_method_uses_most_recent_audit_entry():
    # First attempt was sandbox-fixture; a later, real live re-collection
    # succeeded -- the document's CURRENT method is the most recent one.
    doc = _doc_row("lund_se", "collected")
    audit = {
        "lund_se": [
            dict(_audit_row("lund_se", "sandbox_fetch_tool_substitute")),
            dict(_audit_row("lund_se", "live_http")),
        ]
    }
    assert classify_collection_method(doc, audit) == LIVE_HTTP


def test_classify_collection_method_falls_back_to_manual_verification_status():
    doc = _doc_row(
        "ru_is",
        "collected",
        manual_verification_status="Text retrieved via sandbox fetch tool, not this project's crawler.",
    )
    assert classify_collection_method(doc, {}) == SANDBOX_FIXTURE


def test_classify_collection_method_defaults_to_live_http_by_elimination():
    # No collection_audit row (e.g. a document collected before audit
    # logging existed on the live path) and no sandbox/manual marker in
    # manual_verification_status -- since the sandbox-fixture path always
    # tags its own output, the absence of that tag on a collected document
    # means live HTTP collection, not "unknown". This is exactly the
    # real-world case in the bug report: five documents live-collected
    # locally, with no collection_audit rows yet for that run.
    doc = _doc_row("lund_se", "collected", manual_verification_status=None)
    assert classify_collection_method(doc, {}) == LIVE_HTTP


def test_summarize_collection_methods_all_live_after_real_collection():
    # This is the scenario the bug report describes: after a successful
    # live collection of all five documents, the summary must say so --
    # never keep describing a sandbox-fixture/Lund-failure split.
    rows = [
        _doc_row(uid, "collected") for uid in ["lund_se", "uio_no", "au_dk", "aalto_fi", "ru_is"]
    ]
    audit = [
        _audit_row(uid, "live_http") for uid in ["lund_se", "uio_no", "au_dk", "aalto_fi", "ru_is"]
    ]
    counts = summarize_collection_methods(rows, audit)
    assert counts == {LIVE_HTTP: 5}


def test_render_collection_method_note_reflects_all_live_collected():
    rows = [
        _doc_row(uid, "collected") for uid in ["lund_se", "uio_no", "au_dk", "aalto_fi", "ru_is"]
    ]
    audit = [
        _audit_row(uid, "live_http") for uid in ["lund_se", "uio_no", "au_dk", "aalto_fi", "ru_is"]
    ]
    note = render_collection_method_note(rows, audit)
    assert "5 document(s)" in note
    assert "live collection pipeline" in note
    # The stale sandbox/Lund-specific language must never appear once every
    # document was actually collected live.
    assert "sandbox" not in note.lower()
    assert "Lund" not in note


def test_render_collection_method_note_reflects_mixed_methods_without_hardcoding_names():
    rows = [
        _doc_row("lund_se", "failed"),
        _doc_row("uio_no", "collected"),
        _doc_row("au_dk", "collected"),
        _doc_row("aalto_fi", "collected"),
        _doc_row("ru_is", "collected"),
    ]
    audit = [
        _audit_row("uio_no", "sandbox_fetch_tool_substitute"),
        _audit_row("au_dk", "sandbox_fetch_tool_substitute"),
        _audit_row("aalto_fi", "sandbox_fetch_tool_substitute"),
        _audit_row("ru_is", "sandbox_fetch_tool_substitute"),
        _audit_row("lund_se", "none", outcome="failed"),
    ]
    note = render_collection_method_note(rows, audit)
    # University names are never hardcoded into the note's prose -- only
    # counts per method, computed from the given rows.
    assert "Lund" not in note
    assert "Aalto" not in note
    assert "1 document(s)" in note  # the failed one
    assert "4 document(s)" in note  # the sandbox-fixture ones


def test_render_collection_method_note_empty_database():
    note = render_collection_method_note([], [])
    assert "No documents" in note
