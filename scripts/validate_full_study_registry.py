"""Lightweight structural validation for the Phase 2 registry scaffolding.

Validates config/institutions_full.csv and config/sources_full.csv only.
Does not touch the pilot pipeline, the pilot database, or
config/universities.csv, and does not import anything from
src/nordic_ai_policy_tracker (this is deliberately standalone so it can be
used before any Phase 2 pipeline code exists).

Usage:
    python scripts/validate_full_study_registry.py
Exits 0 on success, 1 if any check fails, printing what failed.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

INSTITUTIONS_CSV = REPO_ROOT / "config" / "institutions_full.csv"
SOURCES_CSV = REPO_ROOT / "config" / "sources_full.csv"

REQUIRED_INSTITUTION_HEADERS = [
    "institution_id",
    "institution_name",
    "country",
    "city",
    "latitude",
    "longitude",
    "institution_type",
    "size_category",
    "technical_or_comprehensive",
    "public_or_private",
    "pilot_overlap",
    "selection_status",
    "selection_rationale",
    "exclusion_rationale",
]

REQUIRED_SOURCE_HEADERS = [
    "source_id",
    "institution_id",
    "source_role",
    "document_type",
    "policy_title",
    "policy_url",
    "file_format",
    "intended_audience",
    "policy_level",
    "original_language",
    "original_language_status",
    "expected_language",
    "verification_status",
    "terms_checked",
    "terms_url",
    "legal_review_status",
    "notes",
]

ALLOWED_SOURCE_ROLES = {"primary_candidate", "supplementary", "primary"}


def read_csv_rows(path: Path) -> tuple[list[str], list[dict]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        rows = [row for row in reader]
    return headers, rows


def validate() -> list[str]:
    errors: list[str] = []

    if not INSTITUTIONS_CSV.exists():
        errors.append(f"missing file: {INSTITUTIONS_CSV}")
    if not SOURCES_CSV.exists():
        errors.append(f"missing file: {SOURCES_CSV}")
    if errors:
        return errors

    inst_headers, inst_rows = read_csv_rows(INSTITUTIONS_CSV)
    src_headers, src_rows = read_csv_rows(SOURCES_CSV)

    if inst_headers != REQUIRED_INSTITUTION_HEADERS:
        errors.append(
            f"institutions_full.csv headers do not match expected schema.\n"
            f"  expected: {REQUIRED_INSTITUTION_HEADERS}\n"
            f"  actual:   {inst_headers}"
        )
    if src_headers != REQUIRED_SOURCE_HEADERS:
        errors.append(
            f"sources_full.csv headers do not match expected schema.\n"
            f"  expected: {REQUIRED_SOURCE_HEADERS}\n"
            f"  actual:   {src_headers}"
        )

    # institution_id uniqueness
    inst_ids = [row["institution_id"] for row in inst_rows if row.get("institution_id")]
    dupes = {i for i in inst_ids if inst_ids.count(i) > 1}
    if dupes:
        errors.append(f"duplicate institution_id values in institutions_full.csv: {sorted(dupes)}")

    # source_id uniqueness
    src_ids = [row["source_id"] for row in src_rows if row.get("source_id")]
    dupes = {i for i in src_ids if src_ids.count(i) > 1}
    if dupes:
        errors.append(f"duplicate source_id values in sources_full.csv: {sorted(dupes)}")

    # every non-empty source references an existing institution
    known_institutions = set(inst_ids)
    for row in src_rows:
        sid = row.get("source_id")
        iid = row.get("institution_id")
        if not sid and not iid:
            continue  # fully blank row, ignore
        if iid not in known_institutions:
            errors.append(f"source_id={sid!r} references unknown institution_id={iid!r}")

    # allowed source_role values
    for row in src_rows:
        role = row.get("source_role")
        if role and role not in ALLOWED_SOURCE_ROLES:
            errors.append(
                f"source_id={row.get('source_id')!r} has disallowed source_role={role!r} "
                f"(allowed: {sorted(ALLOWED_SOURCE_ROLES)})"
            )

    # empty header-only registries are valid at the scaffolding stage --
    # i.e. zero data rows is NOT an error.

    # pilot registry must remain untouched by this validator
    pilot_csv = REPO_ROOT / "config" / "universities.csv"
    if not pilot_csv.exists():
        errors.append(f"pilot registry missing (should be untouched, not deleted): {pilot_csv}")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("Phase 2 registry validation FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(
        "Phase 2 registry validation passed: headers correct, no duplicate ids, "
        "no orphaned sources, no disallowed source_role values, pilot registry present."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
