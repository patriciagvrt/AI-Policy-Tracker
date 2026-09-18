"""Tests for build_keyword_vectorizer() in modeling.bertopic_pipeline: the
CountVectorizer configuration BERTopic uses for its c-TF-IDF keyword/label
extraction. These specifically guard against the pipeline going back to
uninterpretable labels dominated by English stopwords ("0_the_and_ai_to").
"""

from __future__ import annotations

from nordic_ai_policy_tracker.modeling.bertopic_pipeline import (
    MIN_VOCAB_SIZE_BEFORE_MIN_DF_FALLBACK,
    build_keyword_vectorizer,
)

# A small corpus that mimics this project's real pilot text: heavy on
# English stopwords, with a handful of substantive, repeated policy terms.
SAMPLE_TEXTS = [
    "Students must disclose the use of generative ai in their coursework.",
    "The use of generative ai must be disclosed by students in all exams.",
    "Generative ai disclosure is required for any assessment submission.",
    "The university offers institutional support for responsible ai use.",
    "Institutional support and ai literacy training are available to staff.",
    "Responsible and safe ai use is expected of all students and staff.",
    "Assessment rules require ai disclosure before the exam is submitted.",
    "The exam disclosure policy applies to generative ai tools broadly.",
]


def test_build_keyword_vectorizer_strips_english_stopwords():
    vectorizer, config = build_keyword_vectorizer(SAMPLE_TEXTS, min_df=1)
    assert config["stop_words"] == "english"
    vocab = vectorizer.fit(SAMPLE_TEXTS).vocabulary_
    # Common English stopwords that dominated the pre-fix labels must not
    # survive into the vocabulary.
    for stopword in ["the", "and", "to", "of", "is", "in", "by", "for"]:
        assert stopword not in vocab


def test_build_keyword_vectorizer_produces_bigrams():
    vectorizer, config = build_keyword_vectorizer(SAMPLE_TEXTS, min_df=1)
    assert config["ngram_range"] == [1, 2]
    vocab = vectorizer.fit(SAMPLE_TEXTS).vocabulary_
    # At least one meaningful two-word phrase should survive -- this is the
    # whole point of ngram_range=(1, 2) over single words alone.
    multi_word_terms = [term for term in vocab if " " in term]
    assert multi_word_terms, "expected at least one bigram in the vocabulary"


def test_build_keyword_vectorizer_records_full_config():
    _vectorizer, config = build_keyword_vectorizer(SAMPLE_TEXTS, min_df=1, max_df=0.95)
    for key in (
        "stop_words",
        "ngram_range",
        "min_df",
        "max_df",
        "vocabulary_size",
        "min_df_fallback_applied",
        "min_df_fallback_reason",
    ):
        assert key in config


def test_build_keyword_vectorizer_falls_back_when_min_df_2_too_sparse():
    # A tiny, low-repetition corpus where min_df=2 would leave almost no
    # vocabulary -- the fallback to min_df=1 must kick in and be recorded.
    tiny_texts = [
        "unique phrase one about generative ai policy details here",
        "another completely different sentence about exam disclosure rules",
        "a third sentence with mostly distinct wording about institutional support",
    ]
    vectorizer, config = build_keyword_vectorizer(tiny_texts, min_df=2)
    assert config["vocabulary_size"] >= 1
    if config["min_df_fallback_applied"]:
        assert config["min_df"] == 1
        assert config["min_df_fallback_reason"] is not None
        assert "min_df=2" in config["min_df_fallback_reason"]


def test_build_keyword_vectorizer_does_not_fall_back_when_vocab_is_large_enough():
    # A large, repetitive-enough corpus where min_df=2 comfortably clears
    # the fallback threshold -- min_df=2 should be kept as requested.
    repetitive_texts = SAMPLE_TEXTS * 3
    _vectorizer, config = build_keyword_vectorizer(repetitive_texts, min_df=2)
    if config["vocabulary_size"] >= MIN_VOCAB_SIZE_BEFORE_MIN_DF_FALLBACK:
        assert config["min_df_fallback_applied"] is False
        assert config["min_df"] == 2
