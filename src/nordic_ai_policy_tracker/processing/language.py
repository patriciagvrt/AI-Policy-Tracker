"""Language identification.

Uses langdetect (a Python port of Google's language-detection library) to
determine what language a document's cleaned_text is actually written in.
This is a check, not an assumption: a university.csv row saying
expected_language="en" does not guarantee the collected text is English --
a redirect, a partially-translated page, or a login wall could all produce
non-English or near-empty text, and this function is how that gets caught.
"""

from __future__ import annotations

from langdetect import DetectorFactory, LangDetectException, detect, detect_langs

# langdetect's detector is non-deterministic by default (it uses random
# sampling internally for long texts); fixing the seed makes results
# reproducible across runs, which matters for an auditable pipeline.
DetectorFactory.seed = 0

MIN_CHARS_FOR_RELIABLE_DETECTION = 50


def detect_language(text: str) -> str | None:
    """Return the best-guess ISO 639-1 language code, or None if undetectable."""
    if len(text.strip()) < MIN_CHARS_FOR_RELIABLE_DETECTION:
        return None
    try:
        return detect(text)
    except LangDetectException:
        return None


def detect_language_confidence(text: str) -> tuple[str | None, float | None]:
    """Return (language_code, confidence 0-1), or (None, None) if undetectable."""
    if len(text.strip()) < MIN_CHARS_FOR_RELIABLE_DETECTION:
        return None, None
    try:
        candidates = detect_langs(text)
        if not candidates:
            return None, None
        top = candidates[0]
        return top.lang, float(top.prob)
    except LangDetectException:
        return None, None


def confirm_expected_language(text: str, expected_language: str) -> dict:
    """Compare a document's expected_language against what was actually
    detected, returning a small report dict used by the data-quality report.
    """
    detected, confidence = detect_language_confidence(text)
    return {
        "expected_language": expected_language,
        "detected_language": detected,
        "confidence": confidence,
        "matches_expected": detected == expected_language if detected else None,
    }
