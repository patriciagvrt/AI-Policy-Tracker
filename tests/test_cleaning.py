"""Tests for text cleaning / normalization."""

from __future__ import annotations

from nordic_ai_policy_tracker.processing.cleaning import (
    clean_text,
    normalize_whitespace,
    remove_junk_lines,
    remove_repeated_lines,
    strip_personal_contact_info,
)


def test_normalize_whitespace_collapses_spaces_and_blank_lines():
    text = "Hello    world\n\n\n\nSecond   line"
    result = normalize_whitespace(text)
    assert "    " not in result
    assert "\n\n\n" not in result


def test_remove_junk_lines_drops_known_boilerplate():
    text = "Real policy content here.\nSkip to content\nPrint this page\nMore real content."
    result = remove_junk_lines(text)
    assert "Skip to content" not in result
    assert "Print this page" not in result
    assert "Real policy content here." in result


def test_remove_junk_lines_drops_very_short_lines():
    text = "Ok\nThis is a meaningful sentence about AI policy."
    result = remove_junk_lines(text)
    assert "Ok" not in result
    assert "meaningful sentence" in result


def test_remove_repeated_lines_drops_frequent_repeats():
    text = "\n".join(["Header text"] * 5 + ["Unique policy sentence."])
    result = remove_repeated_lines(text, min_repeats=3)
    assert "Header text" not in result
    assert "Unique policy sentence." in result


def test_clean_text_end_to_end():
    raw = "Skip to content\n\n\nStudents must disclose AI use.   \nStudents must disclose AI use.\nStudents must disclose AI use.\nStudents must disclose AI use.\nBack to top"
    result = clean_text(raw)
    assert "Skip to content" not in result
    assert "Back to top" not in result
    # A line repeated 4 times (>= min_repeats=3) is treated as boilerplate and dropped.
    assert "Students must disclose AI use." not in result


# --- Personal-data safeguard: email/phone stripping (compliance correction) -


def test_strip_personal_contact_info_removes_email_addresses():
    text = "Questions? Contact the policy author at jane.doe@example.university.edu for details."
    result = strip_personal_contact_info(text)
    assert "jane.doe@example.university.edu" not in result
    assert "[redacted email]" in result


def test_strip_personal_contact_info_removes_phone_numbers():
    text = "Call the office at +46 46 222 00 00 during business hours."
    result = strip_personal_contact_info(text)
    assert "46 222 00 00" not in result
    assert "[redacted phone]" in result


def test_strip_personal_contact_info_preserves_policy_content():
    text = "Students must disclose AI use in all coursework submissions."
    result = strip_personal_contact_info(text)
    assert result == text


def test_strip_personal_contact_info_does_not_mangle_short_numbers():
    # A section number or a plain year should not be treated as a phone number.
    text = "See section 3.14 of the policy, approved in 2025."
    result = strip_personal_contact_info(text)
    assert "[redacted phone]" not in result


def test_clean_text_pipeline_strips_contact_info():
    raw = "Students must disclose AI use.\nContact ai-policy@university.edu with questions."
    result = clean_text(raw)
    assert "ai-policy@university.edu" not in result
    assert "Students must disclose AI use." in result
