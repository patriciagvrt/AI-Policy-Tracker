"""Content-level tests for the populated config/institutions_full.csv full-study
institution registry (35 institutions, 7 per Nordic country).

Standalone by design (reads the CSV directly via csv.DictReader, no import of
nordic_ai_policy_tracker or the pilot pipeline) -- matches the pattern used by
tests/test_annotation_public_release.py and tests/test_full_study_registry_scaffold.py.
Read-only: never writes to config/institutions_full.csv or config/sources_full.csv.
"""

from __future__ import annotations

import csv
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTITUTIONS_CSV = REPO_ROOT / "config" / "institutions_full.csv"

EXPECTED_COUNTRIES = {"Sweden", "Norway", "Denmark", "Finland", "Iceland"}
EXPECTED_PILOT_OVERLAP_NAMES = {
    "Lund University",
    "University of Oslo",
    "Aarhus University",
    "Aalto University",
    "Reykjavík University",
}

# Column names that would indicate a policy-DOCUMENT source URL has leaked into
# the institution-level registry -- these belong only in sources_full.csv.
POLICY_SOURCE_COLUMN_NAMES = {
    "policy_url",
    "policy_title",
    "source_url",
    "source_id",
    "document_type",
}

# Crude but effective signal that a URL is a specific document rather than an
# institution's homepage.
POLICY_DOCUMENT_URL_MARKERS = (".pdf", ".docx", ".doc", "/policy", "/policies")


def _read_rows() -> list[dict]:
    with INSTITUTIONS_CSV.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _read_header() -> list[str]:
    with INSTITUTIONS_CSV.open(newline="", encoding="utf-8") as f:
        return next(csv.reader(f))


def test_exactly_35_rows():
    rows = _read_rows()
    assert len(rows) == 35, f"expected 35 institutions, found {len(rows)}"


def test_exactly_7_institutions_per_country():
    rows = _read_rows()
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["country"]] = counts.get(row["country"], 0) + 1
    assert set(counts) == EXPECTED_COUNTRIES, counts
    for country, count in counts.items():
        assert count == 7, f"{country} has {count} institutions, expected 7"


def test_unique_institution_ids():
    rows = _read_rows()
    ids = [row["institution_id"] for row in rows]
    assert len(ids) == len(set(ids)), "duplicate institution_id values found"
    assert all(ids), "empty institution_id found"


def test_exactly_5_pilot_overlap_institutions():
    rows = _read_rows()
    overlap_rows = [row for row in rows if row["pilot_overlap"] == "True"]
    assert len(overlap_rows) == 5, [r["institution_name"] for r in overlap_rows]
    overlap_names = {row["institution_name"] for row in overlap_rows}
    assert overlap_names == EXPECTED_PILOT_OVERLAP_NAMES, overlap_names
    # every other row must be explicitly False, never blank/ambiguous
    non_overlap = [
        row for row in rows if row["institution_name"] not in EXPECTED_PILOT_OVERLAP_NAMES
    ]
    assert all(row["pilot_overlap"] == "False" for row in non_overlap)


def test_all_official_websites_populated():
    rows = _read_rows()
    missing = [row["institution_id"] for row in rows if not row["official_website"].strip()]
    assert not missing, f"institutions missing official_website: {missing}"
    # every populated website should at least look like a URL
    for row in rows:
        url = row["official_website"]
        assert url.startswith("http://") or url.startswith("https://"), url


def test_holar_linked_to_hi_is():
    rows = _read_rows()
    by_id = {row["institution_id"]: row for row in rows}
    assert "holar_is" in by_id
    assert "hi_is" in by_id
    holar = by_id["holar_is"]
    assert holar["governance_status"] == "federated_member", holar["governance_status"]
    assert holar["parent_institution_id"] == "hi_is", holar["parent_institution_id"]
    hi = by_id["hi_is"]
    assert hi["governance_status"] == "federation_lead", hi["governance_status"]


def test_no_policy_source_urls_in_institution_registry():
    header = _read_header()
    leaked_columns = POLICY_SOURCE_COLUMN_NAMES & set(header)
    assert (
        not leaked_columns
    ), f"policy-source columns leaked into institution registry: {leaked_columns}"

    rows = _read_rows()
    for row in rows:
        url = row.get("official_website", "")
        lowered = url.lower()
        for marker in POLICY_DOCUMENT_URL_MARKERS:
            assert marker not in lowered, (
                f"{row['institution_id']} official_website looks like a policy "
                f"document URL, not a homepage: {url}"
            )


def test_all_selection_statuses_are_full_study_selected():
    rows = _read_rows()
    statuses = {row["selection_status"] for row in rows}
    assert statuses == {"full_study_selected"}, statuses


def test_iceland_is_national_census_others_are_stratified_sample():
    rows = _read_rows()
    for row in rows:
        if row["country"] == "Iceland":
            assert row["inclusion_method"] == "national_census", row
        else:
            assert row["inclusion_method"] == "stratified_sample", row


def test_governance_status_default_is_independent_except_documented_federation():
    rows = _read_rows()
    for row in rows:
        if row["institution_id"] in ("holar_is",):
            assert row["governance_status"] == "federated_member"
        elif row["institution_id"] == "hi_is":
            assert row["governance_status"] == "federation_lead"
        else:
            assert row["governance_status"] == "independent", row


def test_pilot_registry_and_sources_registry_untouched():
    """This population step is institution-level only: config/sources_full.csv
    must remain header-only, and the pilot config/universities.csv must still
    exist untouched."""
    sources_csv = REPO_ROOT / "config" / "sources_full.csv"
    with sources_csv.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows == [], "sources_full.csv should still be header-only at this stage"

    pilot_csv = REPO_ROOT / "config" / "universities.csv"
    assert pilot_csv.exists()
