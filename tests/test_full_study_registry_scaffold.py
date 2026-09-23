"""Tests for scripts/validate_full_study_registry.py.

These exercise the standalone Phase 2 registry validator against small,
in-memory-style fixture CSVs written to a temp directory -- they never
touch config/institutions_full.csv, config/sources_full.csv, or the pilot
config/universities.csv directly, except for one read-only check that the
real scaffolding files currently pass validation as header-only files.
"""

from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPO_ROOT / "scripts" / "validate_full_study_registry.py"

spec = importlib.util.spec_from_file_location("validate_full_study_registry", VALIDATOR_PATH)
validator = importlib.util.module_from_spec(spec)
sys.modules["validate_full_study_registry"] = validator
spec.loader.exec_module(validator)  # type: ignore[union-attr]


def _write_csv(path: Path, headers: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_header_only_registries_are_valid(tmp_path, monkeypatch):
    inst = tmp_path / "institutions_full.csv"
    src = tmp_path / "sources_full.csv"
    (tmp_path / "config").mkdir()
    pilot = tmp_path / "config" / "universities.csv"
    _write_csv(inst, validator.REQUIRED_INSTITUTION_HEADERS, [])
    _write_csv(src, validator.REQUIRED_SOURCE_HEADERS, [])
    pilot.write_text("university_id\n")

    monkeypatch.setattr(validator, "INSTITUTIONS_CSV", inst)
    monkeypatch.setattr(validator, "SOURCES_CSV", src)
    monkeypatch.setattr(validator, "REPO_ROOT", tmp_path)

    errors = validator.validate()
    assert errors == []


def test_wrong_headers_are_rejected(tmp_path, monkeypatch):
    inst = tmp_path / "institutions_full.csv"
    src = tmp_path / "sources_full.csv"
    pilot = tmp_path / "universities.csv"
    _write_csv(inst, ["institution_id", "institution_name"], [])
    _write_csv(src, validator.REQUIRED_SOURCE_HEADERS, [])
    pilot.write_text("university_id\n")

    monkeypatch.setattr(validator, "INSTITUTIONS_CSV", inst)
    monkeypatch.setattr(validator, "SOURCES_CSV", src)
    monkeypatch.setattr(validator, "REPO_ROOT", tmp_path)

    errors = validator.validate()
    assert any("institutions_full.csv headers" in e for e in errors)


def test_duplicate_institution_id_is_rejected(tmp_path, monkeypatch):
    inst = tmp_path / "institutions_full.csv"
    src = tmp_path / "sources_full.csv"
    pilot = tmp_path / "universities.csv"
    row = {h: "" for h in validator.REQUIRED_INSTITUTION_HEADERS}
    row["institution_id"] = "se_lu"
    _write_csv(inst, validator.REQUIRED_INSTITUTION_HEADERS, [row, dict(row)])
    _write_csv(src, validator.REQUIRED_SOURCE_HEADERS, [])
    pilot.write_text("university_id\n")

    monkeypatch.setattr(validator, "INSTITUTIONS_CSV", inst)
    monkeypatch.setattr(validator, "SOURCES_CSV", src)
    monkeypatch.setattr(validator, "REPO_ROOT", tmp_path)

    errors = validator.validate()
    assert any("duplicate institution_id" in e for e in errors)


def test_orphaned_source_is_rejected(tmp_path, monkeypatch):
    inst = tmp_path / "institutions_full.csv"
    src = tmp_path / "sources_full.csv"
    pilot = tmp_path / "universities.csv"
    _write_csv(inst, validator.REQUIRED_INSTITUTION_HEADERS, [])
    src_row = {h: "" for h in validator.REQUIRED_SOURCE_HEADERS}
    src_row["source_id"] = "src_1"
    src_row["institution_id"] = "does_not_exist"
    _write_csv(src, validator.REQUIRED_SOURCE_HEADERS, [src_row])
    pilot.write_text("university_id\n")

    monkeypatch.setattr(validator, "INSTITUTIONS_CSV", inst)
    monkeypatch.setattr(validator, "SOURCES_CSV", src)
    monkeypatch.setattr(validator, "REPO_ROOT", tmp_path)

    errors = validator.validate()
    assert any("references unknown institution_id" in e for e in errors)


def test_disallowed_source_role_is_rejected(tmp_path, monkeypatch):
    inst = tmp_path / "institutions_full.csv"
    src = tmp_path / "sources_full.csv"
    pilot = tmp_path / "universities.csv"
    inst_row = {h: "" for h in validator.REQUIRED_INSTITUTION_HEADERS}
    inst_row["institution_id"] = "se_lu"
    _write_csv(inst, validator.REQUIRED_INSTITUTION_HEADERS, [inst_row])
    src_row = {h: "" for h in validator.REQUIRED_SOURCE_HEADERS}
    src_row["source_id"] = "src_1"
    src_row["institution_id"] = "se_lu"
    src_row["source_role"] = "not_a_real_role"
    _write_csv(src, validator.REQUIRED_SOURCE_HEADERS, [src_row])
    pilot.write_text("university_id\n")

    monkeypatch.setattr(validator, "INSTITUTIONS_CSV", inst)
    monkeypatch.setattr(validator, "SOURCES_CSV", src)
    monkeypatch.setattr(validator, "REPO_ROOT", tmp_path)

    errors = validator.validate()
    assert any("disallowed source_role" in e for e in errors)


def test_real_scaffolding_files_currently_pass():
    """The actual repo scaffolding files, as of this foundation step, should
    validate cleanly as header-only registries."""
    errors = validator.validate()
    assert errors == [], errors
