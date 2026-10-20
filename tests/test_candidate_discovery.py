"""Tests for policy-source candidate discovery.

Every test here runs against local fixture files under
tests/fixtures/discovery/ via DiscoveryConfig.fixture_root -- no test in
this file makes a real network request.

This file also contains the regression tests added after the real Iceland
discovery run surfaced precision/recall problems: see
docs/candidate_discovery.md and the module docstring in
candidate_discovery.py for what each fix addresses.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from nordic_ai_policy_tracker.discovery import candidate_discovery as cd
from nordic_ai_policy_tracker.discovery.search_terms import (
    POLICY_SIGNAL_TERMS,
    STRONG_TERMS,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "discovery"


def make_config(**overrides) -> cd.DiscoveryConfig:
    defaults = dict(
        user_agent="NordicAIPolicyTrackerBot/0.2 (test; contact: patriciacruz1097@gmail.com)",
        request_delay_seconds=0,
        request_timeout_seconds=5,
        max_retries=1,
        fixture_root=FIXTURES_DIR,
    )
    defaults.update(overrides)
    return cd.DiscoveryConfig(**defaults)


def make_institution(**overrides) -> dict:
    base = {
        "institution_id": "hi_is",
        "institution_name": "Example University",
        "country": "Iceland",
        "official_website": "https://example.hi.is/",
    }
    base.update(overrides)
    return base


# --------------------------------------------------------------------------
# URL normalization / dedup
# --------------------------------------------------------------------------


def test_normalize_url_strips_fragment_and_trailing_slash():
    assert (
        cd.normalize_url("https://Example.hi.is/en/page/#section")
        == "https://example.hi.is/en/page"
    )


def test_normalize_url_root_path_kept_as_slash():
    assert cd.normalize_url("https://example.hi.is") == "https://example.hi.is/"


def test_normalize_url_strips_default_port():
    assert cd.normalize_url("https://example.hi.is:443/en/page") == "https://example.hi.is/en/page"


def test_dedupe_urls_removes_duplicates_preserving_order():
    urls = [
        "https://example.hi.is/en/page",
        "https://example.hi.is/en/other",
        "https://example.hi.is/en/page/",
        "https://example.hi.is/en/page#frag",
    ]
    deduped, removed = cd.dedupe_urls(urls)
    assert deduped == ["https://example.hi.is/en/page", "https://example.hi.is/en/other"]
    assert removed == 2


# --------------------------------------------------------------------------
# Official-domain / subdomain acceptance and deceptive-domain rejection
# (Correction 1 and 2 from the real Iceland run)
# --------------------------------------------------------------------------


def test_is_same_domain_accepts_exact_host():
    assert cd.is_same_domain("https://example.hi.is/en/page", "https://example.hi.is/")


def test_is_same_domain_accepts_genuine_subdomain():
    # setberg.hi.is must be accepted as official for hi.is.
    assert cd.is_same_domain("https://setberg.hi.is/policy", "https://www.hi.is/")
    assert cd.is_same_domain("https://setberg.hi.is/", "https://hi.is/")


def test_is_same_domain_rejects_unrelated_domain():
    assert not cd.is_same_domain("https://other.is/en/page", "https://example.hi.is/")


def test_is_same_domain_rejects_deceptive_domains():
    # These CONTAIN the official domain as a substring/prefix but are a
    # different registrable domain entirely -- must never be accepted.
    assert not cd.is_same_domain("https://hi.is.example.com/fake", "https://www.hi.is/")
    assert not cd.is_same_domain("https://hi.is.evil.example/fake", "https://www.hi.is/")
    assert not cd.is_same_domain("https://nothi.is/fake", "https://www.hi.is/")


# --------------------------------------------------------------------------
# Term matching: left-word-boundary, not arbitrary substring
# (Correction 3 and 4: Kollmar must not match LLM)
# --------------------------------------------------------------------------


def test_match_terms_llm_does_not_match_inside_kollmar():
    # Real false positive from the Iceland run: Iceland University of the
    # Arts candidate "Hekla Kollmar" matched "llm" as a bare substring.
    assert cd.match_terms("Nemandi Hekla Kollmar", STRONG_TERMS) == []
    assert "llm" not in cd.match_terms("Útskriftarverkefni eftir Hekla Kollmar", STRONG_TERMS)


def test_match_terms_llm_matches_as_a_real_term():
    assert cd.match_terms("Using an LLM in the classroom", STRONG_TERMS) == ["llm"]
    assert cd.match_terms("LLM-undirbúningur", STRONG_TERMS) == ["llm"]


def test_match_terms_icelandic_inflected_forms_still_match():
    # Left-boundary-only matching must not break ordinary Icelandic
    # grammar, where case endings are glued directly onto the stem.
    assert "gervigreind" in cd.match_terms("notkun gervigreindarinnar í námi", STRONG_TERMS)
    assert "stefn" in cd.match_terms("marka háskólanum stefnu í notkun", POLICY_SIGNAL_TERMS)


# --------------------------------------------------------------------------
# Strong vs. contextual terms, and the strong-term gate
# (Correction 3, 6, 7: "examinations"/"próf" alone must not create a candidate)
# --------------------------------------------------------------------------


def test_score_candidate_contextual_terms_alone_score_zero_strong_matches():
    result = cd.score_candidate(
        url="https://example.hi.is/english/examinations",
        title="Examinations and Assessment Timetable",
        text_preview="examinations and assessment and examination dates for teaching and learning",
        content_type="html",
    )
    assert result.matched_strong_terms == []


def test_score_candidate_pdf_gets_bonus_point():
    kwargs = dict(
        url="https://example.hi.is/policy",
        title="AI Policy",
        text_preview="artificial intelligence",
    )
    score_html = cd.score_candidate(content_type="html", **kwargs).score
    score_pdf = cd.score_candidate(content_type="pdf", **kwargs).score
    assert score_pdf == score_html + 1


def test_score_candidate_policy_page_scores_higher_than_news_page():
    # Correction: news and research pages must not outrank institutional
    # policy pages that discuss the same topic.
    policy = cd.score_candidate(
        url="https://nested.hi.is/stefna/gervigreind-stefna",
        title="Stefna um ábyrga notkun gervigreindar",
        text_preview="Þessi stefna háskólans fjallar um ábyrga notkun gervigreindar í námi og kennslu",
        content_type="html",
    )
    news = cd.score_candidate(
        url="https://nested.hi.is/news/gervigreind-ai-festival",
        title="Fréttir: Gervigreind á ráðstefnu í ár",
        text_preview="Í dag var fjallað um gervigreind og ChatGPT á ráðstefnu sem haldin var",
        content_type="html",
    )
    assert policy.category == "policy"
    assert news.category == "news"
    assert policy.score > news.score


def test_score_candidate_news_with_strong_term_still_scores_above_zero():
    # News must remain a discoverable lead when it contains a strong AI
    # term -- labeled/penalized, never silently dropped.
    news = cd.score_candidate(
        url="https://nested.hi.is/news/gervigreind-ai-festival",
        title="Fréttir: Gervigreind á ráðstefnu í ár",
        text_preview="Í dag var fjallað um gervigreind og ChatGPT á ráðstefnu",
        content_type="html",
    )
    assert news.category == "news"
    assert news.matched_strong_terms  # has strong terms, so it's still a candidate
    assert news.score > 0
    assert "news" in news.explanation.lower() or "penaliz" in news.explanation.lower()


def test_score_candidate_explanation_is_human_readable_and_nonempty():
    result = cd.score_candidate(
        url="https://example.hi.is/en/ai-guidance-for-students",
        title="Guidance on Generative AI and ChatGPT",
        text_preview="chatgpt chatgpt academic integrity",
        content_type="pdf",
    )
    assert result.explanation
    assert "+" in result.explanation


def test_score_candidate_is_deterministic():
    kwargs = dict(
        url="https://example.hi.is/en/ai-guidance-for-students",
        title="Guidance on Generative AI and ChatGPT",
        text_preview="chatgpt chatgpt chatgpt chatgpt chatgpt chatgpt academic integrity",
        content_type="pdf",
    )
    result1 = cd.score_candidate(**kwargs)
    result2 = cd.score_candidate(**kwargs)
    assert result1.score == result2.score
    assert result1.matched_terms == result2.matched_terms


# --------------------------------------------------------------------------
# Category inference
# --------------------------------------------------------------------------


def test_classify_category_news_url_segment():
    assert (
        cd.classify_category("https://x.is/frettir/something", "Some title", ["chatgpt"]) == "news"
    )


def test_classify_category_policy_signal_term():
    assert (
        cd.classify_category(
            "https://x.is/en/ai-policy", "University AI Policy", ["artificial intelligence"]
        )
        == "policy"
    )


def test_classify_category_unknown_with_no_signals():
    assert cd.classify_category("https://x.is/misc/page", "Misc Page", []) == "unknown"


def test_classify_category_guidance_fallback():
    assert (
        cd.classify_category("https://x.is/library/ai-help", "AI Help", ["chatgpt"]) == "guidance"
    )


# --------------------------------------------------------------------------
# Sitemap parsing (including one level of sitemap-index nesting)
# --------------------------------------------------------------------------


def test_parse_sitemap_xml_urlset():
    xml = """<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.hi.is/a</loc></url>
      <url><loc>https://example.hi.is/b</loc></url>
    </urlset>"""
    pages, nested = cd._parse_sitemap_xml(xml)
    assert pages == ["https://example.hi.is/a", "https://example.hi.is/b"]
    assert nested == []


def test_parse_sitemap_xml_sitemapindex():
    xml = """<?xml version="1.0"?>
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap><loc>https://nested.hi.is/sitemap-a.xml</loc></sitemap>
    </sitemapindex>"""
    pages, nested = cd._parse_sitemap_xml(xml)
    assert pages == []
    assert nested == ["https://nested.hi.is/sitemap-a.xml"]


def test_parse_sitemap_xml_malformed_returns_empty():
    pages, nested = cd._parse_sitemap_xml("not xml at all <<<")
    assert pages == []
    assert nested == []


def test_discover_sitemap_page_urls_follows_one_level_of_nesting():
    transport = cd._FixtureTransport(FIXTURES_DIR)
    config = make_config()
    pages, fetched = cd.discover_sitemap_page_urls(
        transport, ["https://nested.hi.is/sitemap_index.xml"], config
    )
    assert "https://nested.hi.is/en/artificial-intelligence-policy" in pages
    assert "https://nested.hi.is/en/library-hours" in pages
    assert len(fetched) == 3  # the index + its two nested sitemaps


# --------------------------------------------------------------------------
# Institution loading
# --------------------------------------------------------------------------


def test_load_institutions_for_discovery_filters_by_country(tmp_path):
    csv_path = tmp_path / "institutions.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["institution_id", "institution_name", "country", "official_website"]
        )
        writer.writeheader()
        writer.writerow(
            {
                "institution_id": "hi_is",
                "institution_name": "University of Iceland",
                "country": "Iceland",
                "official_website": "https://www.hi.is/",
            }
        )
        writer.writerow(
            {
                "institution_id": "lu_se",
                "institution_name": "Lund University",
                "country": "Sweden",
                "official_website": "https://www.lu.se/",
            }
        )

    iceland_only = cd.load_institutions_for_discovery(csv_path, country="Iceland")
    assert len(iceland_only) == 1
    assert iceland_only[0]["institution_id"] == "hi_is"

    everyone = cd.load_institutions_for_discovery(csv_path, country=None)
    assert len(everyone) == 2


def test_load_institutions_for_discovery_skips_missing_domain(tmp_path):
    csv_path = tmp_path / "institutions.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["institution_id", "institution_name", "country", "official_website"]
        )
        writer.writeheader()
        writer.writerow(
            {
                "institution_id": "no_domain",
                "institution_name": "No Domain U",
                "country": "Iceland",
                "official_website": "",
            }
        )
    rows = cd.load_institutions_for_discovery(csv_path, country="Iceland")
    assert rows == []


# --------------------------------------------------------------------------
# Full per-institution discovery run against fixtures
# --------------------------------------------------------------------------


def test_discover_candidates_for_institution_finds_relevant_pages_only():
    institution = make_institution()
    config = make_config()

    candidates, audit = cd.discover_candidates_for_institution(institution, config)

    urls_found = {c["candidate_url"] for c in candidates}
    assert "https://example.hi.is/en/ai-guidance-for-students" in urls_found
    assert "https://example.hi.is/en/policy/academic-integrity.pdf" in urls_found
    # The cafeteria menu page has no matching keywords in its URL, so the
    # keyword pre-filter should mean it was never even fetched.
    assert "https://example.hi.is/en/cafeteria-menu" not in urls_found
    admin_rows = [
        c for c in candidates if c["candidate_url"] == "https://example.hi.is/admin/dashboard"
    ]
    if admin_rows:
        assert admin_rows[0]["robots_allowed"] == "False"
        assert admin_rows[0]["http_status"] == ""

    assert audit.institution_id == "hi_is"
    assert audit.duplicates_removed >= 0
    assert audit.candidates_found == len(candidates)


def test_discover_candidates_for_institution_respects_full_disallow():
    institution = make_institution(
        institution_id="blocked_is",
        institution_name="Blocked University",
        official_website="https://blocked.hi.is/",
    )
    config = make_config()

    candidates, audit = cd.discover_candidates_for_institution(institution, config)

    assert audit.requests_attempted == 0
    for c in candidates:
        assert c["robots_allowed"] == "False"
        assert c["http_status"] == ""
        assert c["relevance_score"] == 0


def test_discover_candidates_for_institution_follows_nested_sitemap():
    institution = make_institution(
        institution_id="nested_is",
        institution_name="Nested University",
        official_website="https://nested.hi.is/",
    )
    config = make_config()

    candidates, audit = cd.discover_candidates_for_institution(institution, config)

    urls_found = {c["candidate_url"] for c in candidates}
    assert "https://nested.hi.is/en/artificial-intelligence-policy" in urls_found
    assert "https://nested.hi.is/en/library-hours" not in urls_found  # no keyword match
    assert audit.sitemap_urls_found >= 2


def test_discover_candidates_examination_only_page_is_rejected():
    institution = make_institution(
        institution_id="nested_is",
        institution_name="Nested University",
        official_website="https://nested.hi.is/",
    )
    config = make_config()

    candidates, audit = cd.discover_candidates_for_institution(institution, config)

    urls_found = {c["candidate_url"] for c in candidates}
    assert "https://nested.hi.is/english/examinations" not in urls_found
    assert audit.pages_fetched_but_rejected_no_strong_term >= 1


def test_discover_candidates_policy_page_outranks_news_page_end_to_end():
    institution = make_institution(
        institution_id="nested_is",
        institution_name="Nested University",
        official_website="https://nested.hi.is/",
    )
    config = make_config()

    candidates, _ = cd.discover_candidates_for_institution(institution, config)
    by_url = {c["candidate_url"]: c for c in candidates}

    policy_row = by_url["https://nested.hi.is/stefna/gervigreind-stefna"]
    news_row = by_url["https://nested.hi.is/news/gervigreind-ai-festival"]

    assert policy_row["inferred_category"] == "policy"
    assert news_row["inferred_category"] == "news"
    assert int(policy_row["relevance_score"]) > int(news_row["relevance_score"])
    # News remains discoverable -- it's labeled/penalized, not excluded.
    assert int(news_row["relevance_score"]) > 0


def test_discover_candidates_finds_genuine_subdomain():
    # Regression test for the real-world finding: hi.is returned zero
    # candidates even though relevant material existed on a subdomain
    # (setberg.hi.is). The fixture equivalent here is
    # setberg.example.hi.is, linked from example.hi.is's homepage.
    institution = make_institution()
    config = make_config()

    candidates, audit = cd.discover_candidates_for_institution(institution, config)

    urls_found = {c["candidate_url"] for c in candidates}
    assert "setberg.example.hi.is" in audit.subdomains_discovered
    assert any("setberg.example.hi.is" in url for url in urls_found)


def test_discover_candidates_never_touches_sources_or_database():
    """Discovery must never write to config/sources_full.csv or
    data/processed/policy_tracker_full.db. This runs a full discovery pass
    against fixtures and confirms neither real repo file is ever opened in
    a write mode."""
    import builtins

    real_open = builtins.open
    forbidden = ("sources_full.csv", "policy_tracker_full.db")

    def guarded_open(file, mode="r", *args, **kwargs):
        name = str(file)
        if any(f in name for f in forbidden) and any(m in mode for m in ("w", "a", "x", "+")):
            raise AssertionError(f"discovery must never open {name!r} in mode {mode!r}")
        return real_open(file, mode, *args, **kwargs)

    builtins.open = guarded_open
    try:
        institution = make_institution()
        config = make_config()
        candidates, _ = cd.discover_candidates_for_institution(institution, config)
        assert len(candidates) > 0
    finally:
        builtins.open = real_open


# --------------------------------------------------------------------------
# CSV + report writing
# --------------------------------------------------------------------------


def test_write_candidates_csv_has_required_columns(tmp_path):
    institution = make_institution()
    config = make_config()
    candidates, _ = cd.discover_candidates_for_institution(institution, config)

    out_path = tmp_path / "candidates.csv"
    cd.write_candidates_csv(candidates, out_path)

    with out_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == cd.CANDIDATE_CSV_FIELDS
        rows = list(reader)
    assert len(rows) == len(candidates)
    for required in [
        "institution_id",
        "institution_name",
        "country",
        "candidate_url",
        "final_url",
        "page_title",
        "content_type",
        "discovery_method",
        "inferred_category",
        "matched_terms",
        "relevance_score",
        "score_explanation",
        "robots_allowed",
        "http_status",
        "checked_at",
    ]:
        assert required in cd.CANDIDATE_CSV_FIELDS


def test_write_audit_report_mentions_human_review(tmp_path):
    institution = make_institution()
    config = make_config()
    candidates, audit = cd.discover_candidates_for_institution(institution, config)
    result = cd.DiscoveryRunResult(candidates=candidates, institution_audits=[audit])

    out_path = tmp_path / "report.md"
    cd.write_audit_report(result, out_path, country_label="Iceland")

    text = out_path.read_text(encoding="utf-8")
    assert "human review" in text.lower()
    assert "Example University" in text
    assert "Errors: none" in text or "Errors (" in text
    assert "strong AI-specific term" in text or "strong ai-specific term" in text.lower()


def test_run_discovery_across_multiple_institutions():
    institutions = [
        make_institution(),
        make_institution(
            institution_id="nested_is",
            institution_name="Nested University",
            official_website="https://nested.hi.is/",
        ),
    ]
    config = make_config()
    result = cd.run_discovery(institutions, config)
    assert len(result.institution_audits) == 2
    assert len(result.candidates) > 0


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-q"]))
