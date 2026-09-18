"""Tests for configuration loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from nordic_ai_policy_tracker.config import get_settings

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_get_settings_loads_real_settings_file():
    get_settings.cache_clear()
    settings = get_settings()
    assert settings["project"]["name"] == "Nordic University AI Policy Tracker"
    assert "collection" in settings
    assert "paths" in settings


def test_get_settings_missing_file_raises():
    get_settings.cache_clear()
    with pytest.raises(FileNotFoundError):
        get_settings(FIXTURES_DIR / "does_not_exist.yaml")
    get_settings.cache_clear()


def test_get_settings_test_fixture_has_expected_shape():
    get_settings.cache_clear()
    settings = get_settings(FIXTURES_DIR / "settings_test.yaml")
    assert settings["collection"]["request_delay_seconds"] == 0
    assert settings["bertopic"]["min_documents_for_modeling"] == 3
    get_settings.cache_clear()
