"""Text normalization for cleaned_text.

This runs *after* html_extractor/pdf_extractor have already removed
structural boilerplate (nav, footer, etc.) -- this module handles the
remaining text-level noise: repeated whitespace, stray control characters,
duplicated lines (a common artifact of PDF extraction, where a running
header/footer gets pulled out on every page), and very short "lines" that
are almost always leftover UI text ("Skip to content", "Print this page").
"""

from __future__ import annotations

import re
import unicodedata

MIN_MEANINGFUL_LINE_LENGTH = 3

# --- Personal-data safeguard (compliance correction, section 4) ------------
#
# This project analyzes institutions and documents, not individual people.
# It has no business retaining a named individual's direct contact details
# in a stored cleaned_text -- those aren't policy content, and keeping
# them would only create a needless personal-data footprint. These
# patterns are intentionally conservative (favor under- over
# over-matching): a plain-language phone number or a mangled
# obfuscated email is not required to trigger for this safeguard, since
# the numeric/URL identifiers this project actually needs (dates, section
# numbers, statute references) must never be swallowed by an overzealous
# pattern.
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# Matches common phone-number shapes: optional leading +, then digits
# grouped with spaces/dots/dashes/parens, at least 7 digits total so a
# short number sequence (a section "3.14" or a year "2024") is never
# mistaken for a phone number.
PHONE_PATTERN = re.compile(r"(?<!\d)(\+?\d{1,3}[\s.\-]?)?(\(?\d{2,4}\)?[\s.\-]){2,5}\d{2,4}(?!\d)")


def strip_personal_contact_info(text: str) -> str:
    """Removes email addresses and phone-number-shaped sequences from text.

    Data-minimization safeguard: this project stores and displays
    institution-level policy analysis, never a profile or contact record
    for an individual employee, teacher, student, or policy author. Names
    are retained only where they are essential for source attribution
    (e.g. "Office of the Vice-Rector" is fine; a named individual's direct
    line is not something this pipeline needs and it is stripped here
    before text is stored as cleaned_text.
    """
    text = EMAIL_PATTERN.sub("[redacted email]", text)
    text = PHONE_PATTERN.sub(
        lambda m: "[redacted phone]" if sum(c.isdigit() for c in m.group(0)) >= 7 else m.group(0),
        text,
    )
    return text


# Lines that are near-universally boilerplate regardless of site, matched
# case-insensitively as a substring.
JUNK_LINE_PATTERNS = [
    "skip to content",
    "skip to main content",
    "print this page",
    "share this page",
    "back to top",
    "accept cookies",
    "cookie settings",
    "all rights reserved",
]


def normalize_whitespace(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def remove_junk_lines(text: str) -> str:
    kept_lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if len(stripped) < MIN_MEANINGFUL_LINE_LENGTH:
            continue
        lowered = stripped.lower()
        if any(pattern in lowered for pattern in JUNK_LINE_PATTERNS):
            continue
        kept_lines.append(stripped)
    return "\n".join(kept_lines)


def remove_repeated_lines(text: str, min_repeats: int = 3) -> str:
    """Drop lines that repeat verbatim more than `min_repeats` times.

    Extracted PDFs commonly repeat a running header/footer once per page;
    a line repeated across many "pages" of the same document is very
    unlikely to be substantive policy content.
    """
    lines = text.split("\n")
    counts: dict[str, int] = {}
    for line in lines:
        counts[line] = counts.get(line, 0) + 1
    return "\n".join(line for line in lines if counts[line] < min_repeats)


def clean_text(raw_text: str) -> str:
    """Full cleaning pipeline applied to already-extracted main content."""
    text = normalize_whitespace(raw_text)
    text = remove_junk_lines(text)
    text = remove_repeated_lines(text)
    text = strip_personal_contact_info(text)  # personal-data minimization safeguard
    text = normalize_whitespace(text)  # re-collapse blank lines left by removals
    return text
