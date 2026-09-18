"""Hashing helpers for duplicate- and change-detection.

The project needs two related but different things:
1. A stable document_id derived from (university_id, source_url) so the
   same document always gets the same ID across repeated collection runs.
2. A content hash of the cleaned text, so we can tell whether a
   previously-collected document has changed since last time (and skip
   re-downloading/re-processing when it hasn't).
"""

from __future__ import annotations

import hashlib
import re
import unicodedata


def normalize_for_hashing(text: str) -> str:
    """Collapse whitespace and normalize unicode so that trivial formatting
    differences (extra spaces, curly vs straight quotes) don't register as
    a content change.
    """
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def compute_text_hash(text: str) -> str:
    """Return a stable SHA-256 hex digest of the normalized text.

    Used both for duplicate detection (two documents with the same hash are
    identical after normalization) and change detection (re-collecting a
    document and comparing its new hash to the stored one).
    """
    normalized = normalize_for_hashing(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def compute_document_id(university_id: str, source_url: str) -> str:
    """Return a short, stable, deterministic ID for a (university, URL) pair.

    Deterministic means: calling this again with the same inputs always
    returns the same ID, which is what lets us detect "have we already
    collected this document" without needing a database round-trip first.
    """
    key = f"{university_id}::{source_url}".strip().lower()
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
    return f"{university_id}_{digest}"
