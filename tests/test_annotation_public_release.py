"""Tests for the annotation public-release split (Option 4 of
outputs/reports/public_release_audit.md): a scores-only public dataset,
an empty public example template, and the complete evidence file kept
private and git-ignored.

These are deliberately standalone (no dependency on
nordic_ai_policy_tracker's package imports or the live database) so they
can run even before any pipeline code changes for this feature exist, and
so they double as a plain filesystem/Git audit of the release itself.
"""

from __future__ import annotations

import csv
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

PUBLIC_SCORES_CSV = REPO_ROOT / "data" / "annotations" / "pilot_scores_public.csv"
EXAMPLE_TEMPLATE_CSV = REPO_ROOT / "data" / "annotations" / "annotation_template.example.csv"
COMPLETE_LOCAL_CSV = REPO_ROOT / "data" / "annotations" / "annotation_template.csv"
COMPLETE_PRIVATE_CSV = (
    REPO_ROOT / "data" / "annotations" / "private" / "pilot_annotations_complete.csv"
)

# The 18 coding dimensions and their axes, per config/coding_dimensions.yaml,
# duplicated here (not imported) so this test does not depend on that file's
# exact structure -- only on the published data matching this fixed scheme.
REI_DIMENSIONS = {
    "prohibition_restriction",
    "punishment_disciplinary",
    "academic_misconduct_framing",
    "ai_detection_surveillance",
    "mandatory_disclosure",
    "assessment_examination_control",
    "privacy_security_restriction",
}
PISI_DIMENSIONS = {
    "permitted_encouraged_use",
    "ai_literacy",
    "critical_evaluation",
    "responsible_use",
    "teaching_integration",
    "student_support",
    "staff_support",
    "transparency_citation",
    "equity_accessibility_inclusion",
    "privacy_awareness_safe_use",
    "human_oversight_responsibility",
}

EXPECTED_REI_PISI = {
    "aalto_fi": (42.9, 59.1),
    "au_dk": (57.1, 36.4),
    "lund_se": (21.4, 54.5),
    "ru_is": (92.9, 72.7),
    "uio_no": (42.9, 50.0),
}

# SHA-256 hashes recorded immediately before this annotation public-release
# task began (see outputs/reports/public_release_audit.md and this
# conversation's prior verification steps). These must never change here --
# this task does not rerun the pipeline.
EXPECTED_HASHES = {
    "data/processed/policy_tracker.db": "014d2deea2197de5cf77c1620419e0c288a71d514113b3226cb6ab5d9a0f1ac0",
    "data/processed/chunks.parquet": "d0804a360a0d37d96bb3fb282309329651ea6ba12f09dc86b1bcec4504e0f74e",
    "data/processed/topic_assignments.parquet": "f10256b3450d9f4848dc31c87c878d6cbb4122f8d30e9ed91e7a7f482b50d15c",
    "data/processed/topic_labels.parquet": "1d951b49253583101391be6336a3a6299a6e7c30bff3a1cfa9dd7b70c33efd15",
}


def _sha256(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_public_rows() -> list[dict]:
    with PUBLIC_SCORES_CSV.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_public_scores_file_exists():
    assert PUBLIC_SCORES_CSV.exists()


def test_public_scores_has_90_rows():
    rows = _read_public_rows()
    assert len(rows) == 90


def test_public_scores_has_5_documents():
    rows = _read_public_rows()
    doc_ids = {r["document_id"] for r in rows}
    assert len(doc_ids) == 5


def test_every_document_has_18_dimension_scores():
    rows = _read_public_rows()
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["document_id"]] = counts.get(r["document_id"], 0) + 1
    assert len(counts) == 5
    for doc_id, count in counts.items():
        assert count == 18, f"{doc_id} has {count} dimension rows, expected 18"


def test_every_document_has_7_rei_and_11_pisi_dimensions():
    rows = _read_public_rows()
    per_doc_axis: dict[str, dict[str, int]] = {}
    for r in rows:
        d = per_doc_axis.setdefault(r["document_id"], {})
        d[r["axis"]] = d.get(r["axis"], 0) + 1
    for doc_id, axis_counts in per_doc_axis.items():
        assert axis_counts.get("restriction_enforcement") == 7, doc_id
        assert axis_counts.get("pedagogical_support") == 11, doc_id


def test_dimension_ids_match_known_scheme():
    rows = _read_public_rows()
    seen_dims = {r["dimension_id"] for r in rows}
    assert seen_dims == REI_DIMENSIONS | PISI_DIMENSIONS


def test_all_scores_are_0_1_or_2():
    rows = _read_public_rows()
    scores = {r["score"] for r in rows}
    assert scores <= {"0", "1", "2"}
    assert len(rows) > 0


def test_no_evidence_or_timestamp_fields():
    rows = _read_public_rows()
    headers = set(rows[0].keys())
    forbidden_substrings = ["evidence", "timestamp", "offset", "note"]
    for header in headers:
        for bad in forbidden_substrings:
            assert bad not in header.lower(), f"forbidden field present: {header}"


def test_public_coder_identifier_does_not_reveal_name():
    rows = _read_public_rows()
    headers = set(rows[0].keys())
    # No coder-name-bearing column at all (coder_id / coder_name), and no
    # cell anywhere contains the coder's actual name.
    assert "coder_id" not in headers
    assert "coder_name" not in headers
    for r in rows:
        for value in r.values():
            assert "patricia" not in str(value).lower()
            assert "cruz" not in str(value).lower()


def test_scores_reproduce_published_rei_pisi_values():
    rows = _read_public_rows()
    by_uni_axis: dict[tuple[str, str], list[int]] = {}
    for r in rows:
        key = (r["university_id"], r["axis"])
        by_uni_axis.setdefault(key, []).append(int(r["score"]))

    for uni, (expected_rei, expected_pisi) in EXPECTED_REI_PISI.items():
        rei_scores = by_uni_axis[(uni, "restriction_enforcement")]
        pisi_scores = by_uni_axis[(uni, "pedagogical_support")]
        rei_pct = round(100 * sum(rei_scores) / (2 * len(rei_scores)), 1)
        pisi_pct = round(100 * sum(pisi_scores) / (2 * len(pisi_scores)), 1)
        assert rei_pct == expected_rei, f"{uni} REI: got {rei_pct}, expected {expected_rei}"
        assert pisi_pct == expected_pisi, f"{uni} PISI: got {pisi_pct}, expected {expected_pisi}"


def test_example_template_has_headers_but_no_data_rows():
    assert EXAMPLE_TEMPLATE_CSV.exists()
    with EXAMPLE_TEMPLATE_CSV.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        data_rows = list(reader)
    assert len(data_rows) == 0
    assert header == [
        "document_id",
        "university_id",
        "dimension_id",
        "axis",
        "score",
        "evidence_passage",
        "evidence_start_offset",
        "evidence_end_offset",
        "uncertainty_flag",
        "uncertainty_note",
        "coder_id",
        "coding_timestamp",
        "coding_round",
    ]
    # No pilot evidence text anywhere in the example file.
    content = EXAMPLE_TEMPLATE_CSV.read_text(encoding="utf-8")
    assert "patricia" not in content.lower()


def test_complete_annotation_paths_are_git_ignored():
    for rel_path in [
        "data/annotations/annotation_template.csv",
        "data/annotations/private/pilot_annotations_complete.csv",
        "data/annotations/private/",
    ]:
        result = subprocess.run(
            ["git", "check-ignore", "-q", rel_path],
            cwd=REPO_ROOT,
            capture_output=True,
        )
        assert result.returncode == 0, f"{rel_path} is NOT git-ignored"


def test_complete_local_annotation_file_still_present():
    assert COMPLETE_LOCAL_CSV.exists(), (
        "data/annotations/annotation_template.csv must remain physically "
        "present locally -- pilot scripts still read it"
    )
    with COMPLETE_LOCAL_CSV.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 90


def test_private_copy_matches_local_complete_file():
    assert COMPLETE_PRIVATE_CSV.exists()
    assert _sha256(COMPLETE_LOCAL_CSV) == _sha256(COMPLETE_PRIVATE_CSV)


def test_database_and_parquet_files_unchanged():
    for rel_path, expected_hash in EXPECTED_HASHES.items():
        full_path = REPO_ROOT / rel_path
        assert full_path.exists(), f"missing: {rel_path}"
        actual_hash = _sha256(full_path)
        assert (
            actual_hash == expected_hash
        ), f"{rel_path} hash changed: expected {expected_hash}, got {actual_hash}"
