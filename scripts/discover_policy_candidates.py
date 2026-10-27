#!/usr/bin/env python
"""CLI entrypoint for policy-source candidate discovery.

Discovery finds CANDIDATE pages/documents only. It never writes to
config/sources_full.csv and never touches data/processed/policy_tracker_full.db
-- a human researcher must review data/candidates/source_candidates.csv (or
the output path given via --output) and decide what, if anything, belongs
in sources_full.csv. See docs/candidate_discovery.md.

Examples:
    # Iceland only, live network (respects robots.txt and request delay):
    python scripts/discover_policy_candidates.py --country Iceland

    # Dry run against local fixtures, no network access at all:
    python scripts/discover_policy_candidates.py --country Iceland \\
        --fixtures-dir tests/fixtures/discovery
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FULL_STUDY_SETTINGS = REPO_ROOT / "config" / "settings_full_study.yaml"

sys.path.insert(0, str(REPO_ROOT / "src"))

from nordic_ai_policy_tracker.config import get_settings, resolve_path  # noqa: E402
from nordic_ai_policy_tracker.discovery.candidate_discovery import (  # noqa: E402
    build_config_from_settings,
    load_institutions_for_discovery,
    run_discovery,
    write_audit_report,
    write_candidates_csv,
)
from nordic_ai_policy_tracker.utils.logging import get_logger  # noqa: E402

logger = get_logger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--settings",
        default=str(DEFAULT_FULL_STUDY_SETTINGS),
        help="Path to a settings YAML (defaults to config/settings_full_study.yaml, "
        "NOT the pilot config/settings.yaml).",
    )
    parser.add_argument(
        "--country",
        required=True,
        help="Only discover candidates for institutions in this country "
        "(must match a value in config/institutions_full.csv, e.g. Iceland). "
        "This first implementation has only been validated for Iceland.",
    )
    parser.add_argument(
        "--fixtures-dir",
        default=None,
        help="If set, run in dry-run/fixture mode: every 'fetch' is resolved "
        "from local files under this directory instead of making real HTTP "
        "requests. See tests/fixtures/discovery/ for the expected layout.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Override the candidates CSV output path "
        "(defaults to paths.candidates_csv in settings, or "
        "data/candidates/source_candidates.csv).",
    )
    parser.add_argument(
        "--report",
        default=None,
        help="Override the audit report output path "
        "(defaults to outputs/reports/full_study/candidate_discovery_report_<country>.md).",
    )
    parser.add_argument(
        "--max-pages-per-institution",
        type=int,
        default=25,
        help="Cap on candidate pages fetched per institution (default: 25). "
        "Discovery is not full collection.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.country.strip().lower() != "iceland":
        logger.warning(
            "This discovery workflow has only been validated for --country Iceland; "
            "proceeding with %s, but treat results with extra caution.",
            args.country,
        )

    settings = get_settings(args.settings)
    config = build_config_from_settings(settings, fixture_root=args.fixtures_dir)
    config.max_candidate_pages_per_institution = args.max_pages_per_institution

    institutions_csv = resolve_path(settings["paths"]["institutions_csv"])
    institutions = load_institutions_for_discovery(institutions_csv, country=args.country)
    if not institutions:
        logger.error("No institutions found for country=%s in %s", args.country, institutions_csv)
        return 1

    output_path = args.output
    if output_path is None:
        output_path = resolve_path(
            settings["paths"].get("candidates_csv", "data/candidates/source_candidates.csv")
        )

    report_path = args.report
    if report_path is None:
        report_dir = resolve_path(settings["paths"]["report_dir"])
        slug = args.country.strip().lower().replace(" ", "_")
        report_path = Path(report_dir) / f"candidate_discovery_report_{slug}.md"

    logger.info(
        "Starting discovery for %d institution(s) in %s (fixtures: %s)",
        len(institutions),
        args.country,
        args.fixtures_dir or "none -- live network",
    )
    result = run_discovery(institutions, config)

    write_candidates_csv(result.candidates, output_path)
    write_audit_report(result, report_path, country_label=args.country)

    logger.info("Wrote %d candidate(s) to %s", len(result.candidates), output_path)
    logger.info("Wrote audit report to %s", report_path)
    print(f"Candidates: {output_path}")
    print(f"Audit report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
