"""Tests for university-registry loading, active/verified filtering, and
failed-source handling. No live network calls -- uses tests/fixtures/universities_test.csv
and mocks requests where an HTTP call would otherwise be made.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import requests

from nordic_ai_policy_tracker.collection.crawler import (
    AccessDeniedError,
    _polite_get,
    collect_one,
    load_universities,
    read_active_verified_sources,
)
from nordic_ai_policy_tracker.schemas import CollectionStatus, VerificationStatus

FIXTURES_DIR = Path(__file__).parent / "fixtures"
TEST_CSV = FIXTURES_DIR / "universities_test.csv"

TEST_SETTINGS = {
    "collection": {
        "user_agent": "test-agent/0.1",
        "request_delay_seconds": 0,
        "request_timeout_seconds": 5,
        "max_retries": 0,
        "respect_robots_txt": True,
    }
}

# Same as TEST_SETTINGS but with retries enabled, specifically to prove that
# a 403/429 is NOT retried even when max_retries > 0 -- see
# docs/legal_and_compliance.md ("Never bypasses ... rate limits").
TEST_SETTINGS_WITH_RETRIES = {
    "collection": {
        **TEST_SETTINGS["collection"],
        "max_retries": 3,
    }
}


def test_load_universities_parses_all_rows():
    universities = load_universities(TEST_CSV)
    assert len(universities) == 3
    ids = {u.university_id for u in universities}
    assert ids == {"fixture_active", "fixture_inactive", "fixture_unverified"}


def test_load_universities_verification_status_parsed():
    universities = {u.university_id: u for u in load_universities(TEST_CSV)}
    assert universities["fixture_active"].verification_status == VerificationStatus.VERIFIED
    assert universities["fixture_unverified"].verification_status == VerificationStatus.UNVERIFIED


def test_active_source_filtering_only_returns_active_and_verified():
    collectable = read_active_verified_sources(TEST_CSV)
    ids = {u.university_id for u in collectable}
    # fixture_inactive is verified but not active -> excluded.
    # fixture_unverified is active but not verified -> excluded.
    assert ids == {"fixture_active"}


@patch("nordic_ai_policy_tracker.collection.crawler.robots.is_allowed", return_value=True)
@patch("nordic_ai_policy_tracker.collection.crawler.requests.get")
def test_collect_one_failed_source_does_not_raise(mock_get, mock_robots):
    mock_get.side_effect = requests.exceptions.ConnectionError("simulated network failure")
    universities = {u.university_id: u for u in load_universities(TEST_CSV)}
    doc = collect_one(universities["fixture_active"], TEST_SETTINGS)
    assert doc.collection_status == CollectionStatus.FAILED
    assert doc.error_message is not None
    assert "simulated network failure" in doc.error_message


@patch("nordic_ai_policy_tracker.collection.crawler.robots.is_allowed", return_value=False)
def test_collect_one_robots_disallowed_is_skipped_not_failed(mock_robots):
    universities = {u.university_id: u for u in load_universities(TEST_CSV)}
    doc = collect_one(universities["fixture_active"], TEST_SETTINGS)
    assert doc.collection_status == CollectionStatus.SKIPPED_ROBOTS_DISALLOWED
    assert doc.robots_allowed is False


@patch("nordic_ai_policy_tracker.collection.crawler.robots.is_allowed", return_value=True)
@patch("nordic_ai_policy_tracker.collection.crawler.requests.get")
def test_collect_one_stops_immediately_on_403_no_retry(mock_get, mock_robots):
    """A 403 must never be retried, even with max_retries > 0 -- it is
    recorded as a genuine failure on the FIRST attempt, not worked around.
    """
    mock_response = requests.Response()
    mock_response.status_code = 403
    mock_response._content = b"Forbidden"
    mock_get.return_value = mock_response

    universities = {u.university_id: u for u in load_universities(TEST_CSV)}
    doc = collect_one(universities["fixture_active"], TEST_SETTINGS_WITH_RETRIES)

    assert doc.collection_status == CollectionStatus.FAILED
    assert "403" in doc.error_message
    # Exactly one request was made -- no retry loop for a 403.
    assert mock_get.call_count == 1


@patch("nordic_ai_policy_tracker.collection.crawler.robots.is_allowed", return_value=True)
@patch("nordic_ai_policy_tracker.collection.crawler.requests.get")
def test_collect_one_stops_immediately_on_429_no_retry(mock_get, mock_robots):
    mock_response = requests.Response()
    mock_response.status_code = 429
    mock_response._content = b"Too Many Requests"
    mock_get.return_value = mock_response

    universities = {u.university_id: u for u in load_universities(TEST_CSV)}
    doc = collect_one(universities["fixture_active"], TEST_SETTINGS_WITH_RETRIES)

    assert doc.collection_status == CollectionStatus.FAILED
    assert "429" in doc.error_message
    assert mock_get.call_count == 1


@patch("nordic_ai_policy_tracker.collection.crawler.requests.get")
def test_polite_get_raises_access_denied_error_on_403(mock_get):
    mock_response = requests.Response()
    mock_response.status_code = 403
    mock_response._content = b"Forbidden"
    mock_get.return_value = mock_response

    with pytest.raises(AccessDeniedError):
        _polite_get(
            "https://example.edu/policy",
            "test-agent/0.1",
            5,
            max_retries=3,
            request_delay_seconds=0,
        )
    assert mock_get.call_count == 1


def test_collect_one_default_legal_fields_are_honest_unchecked_defaults():
    """Since automated terms-of-use checking isn't implemented, every
    collected document must keep the schema's honest "not yet checked"
    defaults rather than any code guessing at redistribution rights.
    """
    universities = {u.university_id: u for u in load_universities(TEST_CSV)}
    university = universities["fixture_active"]
    assert university.terms_checked is False
    assert university.legal_review_status.value == "pending"


@patch("nordic_ai_policy_tracker.collection.crawler.robots.is_allowed", return_value=True)
@patch("nordic_ai_policy_tracker.collection.crawler.requests.get")
def test_collect_one_success_extracts_and_hashes_text(mock_get, mock_robots):
    html = (FIXTURES_DIR / "sample_policy.html").read_text(encoding="utf-8")
    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response._content = html.encode("utf-8")
    mock_response.headers["Content-Type"] = "text/html; charset=utf-8"
    mock_get.return_value = mock_response

    universities = {u.university_id: u for u in load_universities(TEST_CSV)}
    doc = collect_one(universities["fixture_active"], TEST_SETTINGS)

    assert doc.collection_status == CollectionStatus.COLLECTED
    assert doc.text_hash is not None
    assert doc.word_count > 0
    assert "Skip to content" not in doc.cleaned_text
