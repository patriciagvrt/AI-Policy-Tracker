"""Chunk segmentation for BERTopic and for locating evidence passages.

Two consumers need documents split into smaller pieces:
1. BERTopic, which models topics over chunks, not whole documents (a
   1500-word policy is too heterogeneous a unit for topic modeling).
2. Evidence-passage lookup, where a coder or the rule-based indicator layer
   needs to find the specific sentence(s) that justify a dimension score.

This module tries to avoid splitting sentences unnecessarily: it segments
on paragraph/newline boundaries first, then groups those into chunks of
approximately `chunk_size_tokens` words, only splitting a very long
paragraph mid-sentence as a last resort.
"""

from __future__ import annotations

import re

SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")


def split_into_sentences(text: str) -> list[str]:
    """A lightweight sentence splitter (regex-based, not spaCy) used where
    a full NLP pipeline would be overkill -- e.g. chunk boundary decisions.
    Cleaning.clean_text() and spaCy-based lemmatization elsewhere are the
    heavier tools; this one just needs "good enough" boundaries.
    """
    paragraphs = [p for p in text.split("\n") if p.strip()]
    sentences: list[str] = []
    for paragraph in paragraphs:
        pieces = SENTENCE_BOUNDARY_RE.split(paragraph.strip())
        sentences.extend(p for p in pieces if p.strip())
    return sentences


def chunk_document(
    text: str,
    chunk_size_tokens: int = 200,
    chunk_overlap_tokens: int = 40,
) -> list[str]:
    """Split `text` into overlapping chunks of roughly `chunk_size_tokens`
    words, without breaking sentences apart where avoidable.

    Overlap exists so a concept discussed right at a chunk boundary doesn't
    get split across two chunks with neither having full context.
    """
    if chunk_overlap_tokens >= chunk_size_tokens:
        raise ValueError("chunk_overlap_tokens must be smaller than chunk_size_tokens")

    sentences = split_into_sentences(text)
    if not sentences:
        return []

    chunks: list[str] = []
    current_sentences: list[str] = []
    current_word_count = 0

    for sentence in sentences:
        sentence_word_count = len(sentence.split())
        if current_word_count + sentence_word_count > chunk_size_tokens and current_sentences:
            chunks.append(" ".join(current_sentences))
            # Build overlap: keep trailing sentences whose combined word
            # count is closest to chunk_overlap_tokens, for context continuity.
            overlap_sentences: list[str] = []
            overlap_word_count = 0
            for s in reversed(current_sentences):
                w = len(s.split())
                if overlap_word_count + w > chunk_overlap_tokens:
                    break
                overlap_sentences.insert(0, s)
                overlap_word_count += w
            current_sentences = overlap_sentences
            current_word_count = overlap_word_count

        current_sentences.append(sentence)
        current_word_count += sentence_word_count

    if current_sentences:
        chunks.append(" ".join(current_sentences))

    return chunks
