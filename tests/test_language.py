"""Tests for language detection / confirmation."""

from __future__ import annotations

from nordic_ai_policy_tracker.processing.language import confirm_expected_language, detect_language


def test_detect_language_english_text():
    text = (
        "Students are encouraged to use generative AI tools to support their "
        "learning, provided that use is disclosed to instructors."
    )
    assert detect_language(text) == "en"


def test_detect_language_short_text_returns_none():
    assert detect_language("Hi") is None


def test_confirm_expected_language_matches():
    text = "This policy explains how students should disclose the use of generative AI tools in coursework."
    report = confirm_expected_language(text, expected_language="en")
    assert report["expected_language"] == "en"
    assert report["detected_language"] == "en"
    assert report["matches_expected"] is True


def test_confirm_expected_language_unknown_for_too_short_text():
    report = confirm_expected_language("Hi", expected_language="en")
    assert report["detected_language"] is None
    assert report["matches_expected"] is None
