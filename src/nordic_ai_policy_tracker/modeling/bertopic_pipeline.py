"""BERTopic pipeline for exploratory thematic discovery.

Explicit scope limits, enforced in code (not just documentation):
- This module NEVER converts a topic probability into a REI/PISI score.
- With fewer documents/chunks than `min_documents_for_modeling` in
  config/settings.yaml, `run_topic_model()` refuses to fabricate a model
  and instead raises InsufficientDataError with a clear message. The
  caller (scripts/train_topics.py) catches this and writes an
  "experimental / not run" marker to outputs rather than silently
  producing an empty or misleading topic list.
- All parameters used (embedding model name, random seed, min_topic_size)
  are recorded alongside the output, since "what parameters produced this"
  is part of what makes a topic model result auditable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from nordic_ai_policy_tracker.schemas import TopicChunk


class InsufficientDataError(Exception):
    """Raised when there isn't enough data for a meaningful topic model."""


# Minimum resulting vocabulary size before we consider min_df=2 to have
# thrown away too much of a small corpus. Below this, BERTopic's c-TF-IDF
# keyword extraction has too little left to produce interpretable labels,
# which defeats the purpose of tightening the vectorizer in the first
# place. This is a documented, deliberate threshold, not a magic number --
# see build_keyword_vectorizer()'s docstring.
MIN_VOCAB_SIZE_BEFORE_MIN_DF_FALLBACK = 15


def build_keyword_vectorizer(
    texts: list[str],
    min_df: int = 2,
    max_df: float = 0.95,
    ngram_range: tuple[int, int] = (1, 2),
):
    """Builds the CountVectorizer BERTopic uses for its c-TF-IDF keyword
    extraction (the step that produces each topic's label/keywords) --
    this is separate from, and has nothing to do with, whichever model
    produces the chunk EMBEDDINGS used for clustering.

    Configuration and rationale:
    - stop_words="english": removes exactly the kind of generic filler
      ("the", "and", "to") that was dominating this pilot's topic labels
      before this change (e.g. "0_the_and_ai_to").
    - ngram_range=(1, 2): keeps both single words and two-word phrases
      (e.g. "generative ai", "exam disclosure"), which are usually far
      more interpretable than single words alone for policy text.
    - min_df=2 (default): a term must appear in at least 2 chunks to be
      considered -- this filters out one-off phrasings/typos/noise
      specific to a single chunk, which is meaningful for even a small
      corpus, since it targets repetition across chunks, not an absolute
      count that scales with corpus size.
    - max_df=0.95: drops terms appearing in more than 95% of chunks --
      these are corpus-wide boilerplate (e.g. a term appearing in nearly
      every chunk regardless of topic) that a c-TF-IDF label gains
      nothing from keeping, without requiring a hand-curated
      project-specific stopword list.

    Fallback: with a corpus as small as this pilot's (order of dozens of
    chunks), min_df=2 can legitimately strip out too much vocabulary --
    if the resulting vocabulary would be smaller than
    MIN_VOCAB_SIZE_BEFORE_MIN_DF_FALLBACK, this function automatically
    retries with min_df=1 and records that fact in the returned config
    (`min_df_fallback_applied`), rather than silently returning a
    vectorizer BERTopic can barely extract keywords from. A
    project-specific custom stopword list was deliberately NOT added on
    top of stop_words="english" + max_df: doing so without first
    reviewing actual over-frequent corpus terms would risk removing a
    substantively important word (e.g. "disclosure", "assessment") on a
    guess, which this project's own rules disallow -- max_df=0.95 already
    achieves the same corpus-adaptive effect in a way that requires no
    manual word list to maintain.

    Returns:
        (vectorizer, config) -- config is a plain dict of every setting
        actually used (after any fallback), suitable for recording
        verbatim in the topic-model report.
    """
    from sklearn.feature_extraction.text import CountVectorizer

    def _fit_probe(min_df_value: int) -> tuple[object, int]:
        probe = CountVectorizer(
            stop_words="english",
            ngram_range=ngram_range,
            min_df=min_df_value,
            max_df=max_df,
        )
        probe.fit(texts)
        return probe, len(probe.vocabulary_)

    vectorizer, vocab_size = _fit_probe(min_df)
    min_df_fallback_applied = False
    fallback_reason = None

    if vocab_size < MIN_VOCAB_SIZE_BEFORE_MIN_DF_FALLBACK and min_df > 1:
        fallback_vectorizer, fallback_vocab_size = _fit_probe(1)
        if fallback_vocab_size > vocab_size:
            fallback_reason = (
                f"min_df={min_df} produced only {vocab_size} vocabulary term(s) on this "
                f"{len(texts)}-chunk corpus (below the "
                f"{MIN_VOCAB_SIZE_BEFORE_MIN_DF_FALLBACK}-term threshold this project treats as "
                "too thin for interpretable c-TF-IDF keywords), so min_df=1 was used instead, "
                f"yielding {fallback_vocab_size} term(s). See build_keyword_vectorizer()'s "
                "docstring for the full rationale."
            )
            vocab_size = fallback_vocab_size
            min_df_fallback_applied = True
            min_df = 1

    config = {
        "stop_words": "english",
        "ngram_range": list(ngram_range),
        "min_df": min_df,
        "max_df": max_df,
        "vocabulary_size": vocab_size,
        "min_df_fallback_applied": min_df_fallback_applied,
        "min_df_fallback_reason": fallback_reason,
    }
    # Return a fresh, unfit vectorizer with the final settings -- BERTopic
    # fits its own copy internally, and re-using an already-fit instance
    # across corpora/runs would be a subtle bug.
    from sklearn.feature_extraction.text import CountVectorizer as _CV

    final_vectorizer = _CV(
        stop_words="english",
        ngram_range=ngram_range,
        min_df=min_df,
        max_df=max_df,
    )
    return final_vectorizer, config


@dataclass
class TopicModelResult:
    topic_chunks: list[TopicChunk]
    topic_info: list[dict]  # one row per topic: id, size, keywords
    representative_docs: dict[int, list[str]]  # topic_id -> representative chunk texts
    topic_keywords: dict[int, list[str]] = field(default_factory=dict)  # topic_id -> keyword list
    parameters: dict = field(default_factory=dict)
    is_experimental: bool = True  # always True for this pilot's corpus size


def run_topic_model(
    chunks: list[TopicChunk],
    embedding_model_name: str = "all-MiniLM-L6-v2",
    random_seed: int = 42,
    min_topic_size: int = 3,
    min_documents_for_modeling: int = 3,
) -> TopicModelResult:
    """Fit a BERTopic model over the given chunks.

    Raises:
        InsufficientDataError: if there are fewer distinct source documents
            than min_documents_for_modeling, or fewer chunks than
            min_topic_size * 2 (BERTopic needs enough points to form even
            one cluster meaningfully). This is a deliberate hard stop, not
            a warning that gets ignored -- see module docstring.
    """
    distinct_documents = {c.document_id for c in chunks}
    if len(distinct_documents) < min_documents_for_modeling:
        raise InsufficientDataError(
            f"Only {len(distinct_documents)} distinct document(s) have chunks; "
            f"need at least {min_documents_for_modeling} for a topic model that "
            "isn't just re-describing a single source. Refusing to fabricate a "
            "topic model on data this thin."
        )
    if len(chunks) < min_topic_size * 2:
        raise InsufficientDataError(
            f"Only {len(chunks)} chunk(s) available; need at least {min_topic_size * 2} "
            "to fit even a minimal topic model. Refusing to fabricate topics."
        )

    # Imports deferred to inside the function: bertopic/sentence-transformers
    # are heavy dependencies, and importing them at module load time would
    # slow down every script that imports this module even when it never
    # calls run_topic_model (e.g. the dashboard's non-topic pages).
    from bertopic import BERTopic
    from umap import UMAP

    texts = [c.chunk_text for c in chunks]
    embedding_source = embedding_model_name
    embedder_for_bertopic = None  # only set when a real sentence-transformer loads
    # topic_method / semantic_embeddings_used are the explicit, machine-checkable
    # fields the compliance correction requires: a reader (or a test) can tell
    # which embedding actually produced a given topic run without parsing the
    # free-text embedding_source string above.
    topic_method = "bertopic_sentence_transformer"
    semantic_embeddings_used = True

    try:
        from sentence_transformers import SentenceTransformer

        embedder = SentenceTransformer(embedding_model_name)
        embeddings = embedder.encode(texts, show_progress_bar=False)
        embedder_for_bertopic = embedder
    except Exception as exc:
        # Typically a network failure downloading the model (e.g. this
        # project's build sandbox cannot reach huggingface.co). Rather than
        # letting the whole pipeline fail with no output, fall back to a
        # purely local TF-IDF embedding via scikit-learn. This is NOT a
        # silent substitution: embedding_source (and the explicit
        # topic_method/topic_status/semantic_embeddings_used fields below)
        # are recorded in the returned parameters so every consumer of this
        # result can see which embedding actually produced it. This fallback
        # output is NOT the final BERTopic analysis -- see
        # dashboard/components/labels.py:BERTOPIC_DISCLAIMER and
        # docs/methodology.md. The model should be re-run locally with
        # network access to huggingface.co so the configured
        # sentence-transformer can actually be used.
        from sklearn.feature_extraction.text import TfidfVectorizer

        vectorizer = TfidfVectorizer(max_features=200, stop_words="english")
        embeddings = vectorizer.fit_transform(texts).toarray()
        embedding_source = (
            f"tfidf_fallback (sentence-transformer unavailable: {type(exc).__name__})"
        )
        topic_method = "tfidf_fallback"
        semantic_embeddings_used = False

    # UMAP's own random_state makes the dimensionality-reduction step
    # reproducible; BERTopic uses UMAP internally by default, so we build
    # and pass one explicitly rather than relying on BERTopic's default
    # (which would use a non-fixed seed).
    umap_model = UMAP(
        random_state=random_seed,
        n_neighbors=min(15, max(2, len(texts) - 1)),
        n_components=min(5, max(2, len(texts) - 2)),
    )

    # Keyword/label vectorizer -- a separate concern from the embedding
    # model above: this controls what BERTopic's c-TF-IDF step considers
    # when it picks each topic's keywords/label, not how chunks are
    # embedded/clustered. See build_keyword_vectorizer()'s docstring.
    #
    # Important wrinkle, discovered by actually running this against a real
    # corpus: BERTopic does NOT fit this vectorizer on the individual chunk
    # texts. It concatenates all chunks belonging to each topic into one
    # "document" per topic and fits the vectorizer on THAT much smaller set
    # (one row per topic -- as few as 2-3 for a small corpus like this
    # pilot's). A min_df evaluated against 29 chunks can therefore still be
    # unusable once applied to only a handful of topic-level documents:
    # scikit-learn raises ValueError("max_df corresponds to < documents
    # than min_df") whenever max_df * n_topic_documents < min_df, which is
    # easy to hit with min_df=2 and only 2-4 topics. build_keyword_vectorizer()
    # cannot predict the eventual topic count up front (clustering hasn't
    # happened yet), so this is handled here as an explicit runtime
    # fallback: if fitting fails with that specific error, we retry once
    # with min_df=1 (the only value guaranteed to be valid for any topic
    # count >= 1) and record that this second-level fallback was needed.
    keyword_vectorizer, vectorizer_config = build_keyword_vectorizer(texts)
    vectorizer_config["runtime_min_df_retry_applied"] = False

    topic_model = BERTopic(
        embedding_model=embedder_for_bertopic,
        umap_model=umap_model,
        vectorizer_model=keyword_vectorizer,
        min_topic_size=min_topic_size,
        calculate_probabilities=True,
        verbose=False,
    )
    try:
        topics, probabilities = topic_model.fit_transform(texts, embeddings)
    except ValueError as exc:
        if "max_df corresponds to < documents than min_df" not in str(exc):
            raise
        from sklearn.feature_extraction.text import CountVectorizer as _CV

        original_min_df = vectorizer_config["min_df"]
        retry_vectorizer = _CV(
            stop_words="english",
            ngram_range=tuple(vectorizer_config["ngram_range"]),
            min_df=1,
            max_df=vectorizer_config["max_df"],
        )
        vectorizer_config["min_df"] = 1
        vectorizer_config["runtime_min_df_retry_applied"] = True
        vectorizer_config["runtime_min_df_retry_reason"] = (
            "BERTopic fits this vectorizer on one concatenated document per discovered "
            "topic, not on individual chunks -- with this run's small topic count, "
            f"min_df={original_min_df} left too few (or zero) valid topic-level documents "
            "for scikit-learn's max_df/min_df bounds, so min_df=1 was used instead. See the "
            "comment above this retry in run_topic_model()."
        )
        topic_model = BERTopic(
            embedding_model=embedder_for_bertopic,
            umap_model=umap_model,
            vectorizer_model=retry_vectorizer,
            min_topic_size=min_topic_size,
            calculate_probabilities=True,
            verbose=False,
        )
        topics, probabilities = topic_model.fit_transform(texts, embeddings)

    updated_chunks: list[TopicChunk] = []
    for chunk, topic_id, prob in zip(chunks, topics, probabilities, strict=True):
        # `prob` from calculate_probabilities=True is an array over all
        # topics for outlier-aware models; take the max as this chunk's
        # confidence in its assigned topic.
        try:
            topic_probability = float(max(prob)) if hasattr(prob, "__len__") else float(prob)
        except (TypeError, ValueError):
            topic_probability = None
        updated_chunks.append(
            chunk.model_copy(
                update={
                    "topic_id": int(topic_id),
                    "topic_probability": topic_probability,
                    "is_outlier": topic_id == -1,
                }
            )
        )

    topic_info_df = topic_model.get_topic_info()
    topic_info = topic_info_df.to_dict(orient="records")

    # Per-topic keyword lists from the c-TF-IDF step (using the vectorizer
    # above), for TopicLabel.top_keywords -- kept separate from the
    # automatic *label* string, which is just these same keywords joined.
    topic_keywords: dict[int, list[str]] = {}
    for topic_id in topic_info_df["Topic"]:
        if topic_id == -1:
            continue
        try:
            words_scores = topic_model.get_topic(int(topic_id))
            topic_keywords[int(topic_id)] = (
                [word for word, _score in words_scores] if words_scores else []
            )
        except Exception:
            topic_keywords[int(topic_id)] = []

    representative_docs: dict[int, list[str]] = {}
    for topic_id in topic_info_df["Topic"]:
        if topic_id == -1:
            continue
        try:
            reps = topic_model.get_representative_docs(topic_id)
            representative_docs[int(topic_id)] = reps[:3] if reps else []
        except Exception:
            representative_docs[int(topic_id)] = []

    return TopicModelResult(
        topic_chunks=updated_chunks,
        topic_info=topic_info,
        representative_docs=representative_docs,
        topic_keywords=topic_keywords,
        parameters={
            "embedding_model_requested": embedding_model_name,
            "embedding_model_actually_used": embedding_source,
            "topic_method": topic_method,  # "bertopic_sentence_transformer" | "tfidf_fallback"
            "topic_status": "experimental",  # always -- see module docstring / BERTOPIC_DISCLAIMER
            "semantic_embeddings_used": semantic_embeddings_used,
            "random_seed": random_seed,
            "min_topic_size": min_topic_size,
            "n_chunks": len(chunks),
            "n_documents": len(distinct_documents),
            # Keyword/label vectorizer config -- see build_keyword_vectorizer()'s
            # docstring for full rationale, including the min_df fallback logic.
            "keyword_vectorizer": vectorizer_config,
        },
        is_experimental=True,
    )
