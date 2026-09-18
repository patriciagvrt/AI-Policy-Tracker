"""Duplicate document detection.

Two documents are treated as duplicates if their cleaned_text hashes match
exactly (see utils/text_hashing.py) after normalization. This project
intentionally does not attempt fuzzy/near-duplicate detection in the pilot
(e.g. minhash/simhash) -- with five documents the risk of near-duplicates
is low and exact-hash matching is transparent and easy to audit. A TODO for
the 30+ university expansion is noted in docs/limitations.md, not as a
silent gap here.
"""

from __future__ import annotations

from nordic_ai_policy_tracker.schemas import PolicyDocument


def find_exact_duplicates(documents: list[PolicyDocument]) -> dict[str, str]:
    """Return a mapping {document_id: duplicate_of_document_id} for any
    document whose text_hash matches an earlier document's hash.

    The first document encountered with a given hash is treated as the
    canonical one; later documents sharing that hash point to it.
    """
    seen_hash_to_doc_id: dict[str, str] = {}
    duplicates: dict[str, str] = {}
    for doc in documents:
        if not doc.text_hash:
            continue
        if doc.text_hash in seen_hash_to_doc_id:
            duplicates[doc.document_id] = seen_hash_to_doc_id[doc.text_hash]
        else:
            seen_hash_to_doc_id[doc.text_hash] = doc.document_id
    return duplicates


def mark_duplicates(documents: list[PolicyDocument]) -> list[PolicyDocument]:
    """Return a new list with duplicate_of set on any duplicate documents."""
    duplicate_map = find_exact_duplicates(documents)
    updated: list[PolicyDocument] = []
    for doc in documents:
        if doc.document_id in duplicate_map:
            doc = doc.model_copy(update={"duplicate_of": duplicate_map[doc.document_id]})
        updated.append(doc)
    return updated


def has_content_changed(previous_hash: str | None, new_hash: str | None) -> bool:
    """True if this looks like genuinely new/changed content (used to
    decide whether to skip re-processing an unchanged document on a
    repeat collection run).
    """
    if previous_hash is None or new_hash is None:
        return True
    return previous_hash != new_hash
