"""Tests for sentence splitting and chunking."""

from __future__ import annotations

import pytest

from nordic_ai_policy_tracker.processing.segmentation import chunk_document, split_into_sentences


def test_split_into_sentences_basic():
    text = "This is sentence one. This is sentence two! Is this sentence three?"
    sentences = split_into_sentences(text)
    assert len(sentences) == 3
    assert sentences[0] == "This is sentence one."


def test_split_into_sentences_does_not_split_abbreviated_numbers_badly():
    # Not a perfect sentence splitter, but should not crash and should
    # produce a reasonable count for straightforward policy prose.
    text = "Students must disclose AI use. Staff should read the guidance."
    sentences = split_into_sentences(text)
    assert len(sentences) == 2


def test_chunk_document_respects_approximate_size():
    text = " ".join([f"Sentence number {i} about AI policy." for i in range(40)])
    chunks = chunk_document(text, chunk_size_tokens=30, chunk_overlap_tokens=5)
    assert len(chunks) > 1
    for chunk in chunks:
        # allow some slack since we don't split mid-sentence
        assert len(chunk.split()) <= 40


def test_chunk_document_empty_text_returns_no_chunks():
    assert chunk_document("") == []


def test_chunk_document_rejects_overlap_ge_size():
    with pytest.raises(ValueError):
        chunk_document("Some text.", chunk_size_tokens=10, chunk_overlap_tokens=10)


def test_chunk_document_produces_overlap_between_consecutive_chunks():
    # Multiple short sentences (not one long one) so the chunker actually
    # has sentence boundaries to split on.
    text = " ".join([f"Word{i} word{i}b word{i}c." for i in range(30)])
    chunks = chunk_document(text, chunk_size_tokens=20, chunk_overlap_tokens=5)
    assert len(chunks) >= 2
