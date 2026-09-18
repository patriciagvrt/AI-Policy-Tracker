"""A small, fixed categorical color assignment for the five Nordic countries.

Per the project's dataviz guidance: categorical hues are assigned in a
fixed order (by country here), never cycled or reassigned when a filter
changes which countries are visible, so a country's color stays constant
across every chart and every filter state.
"""

from __future__ import annotations

# Fixed, deliberately distinct hues (not a generated/cycled palette).
# Chosen for reasonable colorblind-safe separation at categorical count 5.
COUNTRY_COLORS: dict[str, str] = {
    "Sweden": "#2E5EAA",  # blue
    "Norway": "#C0392B",  # red
    "Denmark": "#E67E22",  # orange
    "Finland": "#27AE60",  # green
    "Iceland": "#8E44AD",  # purple
}

DEFAULT_COLOR = "#7F8C8D"  # muted gray fallback for any unexpected category


def color_for_country(country: str) -> str:
    return COUNTRY_COLORS.get(country, DEFAULT_COLOR)
