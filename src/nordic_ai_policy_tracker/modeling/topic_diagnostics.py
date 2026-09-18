"""Diagnostics for whether a BERTopic topic reflects a general policy theme
or is really just picking up on one source: a single university's writing
style, one document type's boilerplate, or vocabulary specific to a single
institution's document rather than a theme shared across the corpus.

None of this changes what a topic IS (that's bertopic_pipeline.py's job).
These functions only describe, after the fact, how concentrated each
topic's chunks are by university and by document type, so a reader (or the
topic_model_report.md this feeds) can judge whether a topic is a genuine
cross-institution theme or an artifact of one source dominating a small
cluster -- which is a real risk in a corpus this small (a handful of
documents, dozens of chunks).

Nothing here is computed from BERTopic's model object -- only from the
chunk -> topic assignments (TopicChunk-like rows) joined against each
chunk's document_id -> (university_id, document_type) metadata. That keeps
this module usable in tests without needing to fit a real model.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict

# A topic where more than this fraction of its chunks come from a single
# university is flagged as potentially institution-specific rather than a
# general theme. Chosen per the project's own requirement (70%) -- not an
# empirical threshold, just the line this project has decided to flag at.
INSTITUTION_DOMINANCE_THRESHOLD = 0.70


def _document_metadata_index(document_rows: list) -> dict[str, dict]:
    """Builds document_id -> {university_id, university_name, document_type}
    from a list of documents-table rows (sqlite3.Row or dict-like).
    """
    index: dict[str, dict] = {}
    for row in document_rows:
        index[row["document_id"]] = {
            "university_id": row["university_id"],
            "university_name": row["university_name"],
            "document_type": row["document_type"],
        }
    return index


def _topic_entropy(counts: list[int]) -> float:
    """Shannon entropy (base 2) of a topic's chunk counts across whatever
    it's grouped by (university, in this module's use). 0.0 means every
    chunk came from a single group (maximally concentrated); higher values
    mean chunks are spread more evenly across groups. This is a standard,
    transparent diversity measure -- not a novel or tuned statistic.
    """
    total = sum(counts)
    if total == 0:
        return 0.0
    entropy = 0.0
    for count in counts:
        if count == 0:
            continue
        p = count / total
        entropy -= p * math.log2(p)
    return entropy


def compute_topic_university_table(
    topic_chunks: list,
    document_rows: list,
) -> list[dict]:
    """One row per (topic_id, university), excluding outlier chunks
    (topic_id == -1, which by definition isn't a coherent topic).

    Each row reports:
      - topic_id, university_id, university_name
      - chunk_count: chunks from this university assigned to this topic
      - pct_of_topic: chunk_count / (total chunks in this topic)
      - pct_of_university: chunk_count / (total chunks from this university,
        across ALL topics including outliers -- "how much of this
        university's material landed in this topic")
    """
    doc_meta = _document_metadata_index(document_rows)

    # chunks per topic (denominator for pct_of_topic)
    topic_totals: Counter = Counter()
    # chunks per university, across all topics+outliers (denominator for pct_of_university)
    university_totals: Counter = Counter()
    # (topic_id, university_id) -> chunk_count
    pair_counts: Counter = Counter()
    university_names: dict[str, str] = {}

    for chunk in topic_chunks:
        meta = doc_meta.get(chunk.document_id)
        if meta is None:
            continue
        university_id = meta["university_id"]
        university_names[university_id] = meta["university_name"]
        university_totals[university_id] += 1
        if chunk.topic_id is None or chunk.topic_id == -1:
            continue
        topic_totals[chunk.topic_id] += 1
        pair_counts[(chunk.topic_id, university_id)] += 1

    rows = []
    for (topic_id, university_id), count in sorted(pair_counts.items()):
        topic_total = topic_totals[topic_id]
        university_total = university_totals[university_id]
        rows.append(
            {
                "topic_id": topic_id,
                "university_id": university_id,
                "university_name": university_names.get(university_id, university_id),
                "chunk_count": count,
                "pct_of_topic": round(100 * count / topic_total, 1) if topic_total else 0.0,
                "pct_of_university": (
                    round(100 * count / university_total, 1) if university_total else 0.0
                ),
            }
        )
    return rows


def compute_institution_dominance(
    topic_chunks: list,
    document_rows: list,
) -> list[dict]:
    """Per-topic summary: dominant university, its share of the topic's
    chunks, how many distinct universities contributed to the topic, the
    topic's entropy across universities, and whether it crosses the
    INSTITUTION_DOMINANCE_THRESHOLD flag.

    A flagged topic is NOT discarded or hidden -- flagging only means the
    report must carry the caveat that an institution-dominated topic may
    reflect that source's writing style, document type, or vocabulary
    rather than a theme shared across the corpus (see
    scripts/train_topics.py's report text).
    """
    university_table = compute_topic_university_table(topic_chunks, document_rows)
    by_topic: dict[int, list[dict]] = defaultdict(list)
    for row in university_table:
        by_topic[row["topic_id"]].append(row)

    summary = []
    for topic_id, rows in sorted(by_topic.items()):
        rows_sorted = sorted(rows, key=lambda r: r["chunk_count"], reverse=True)
        dominant = rows_sorted[0]
        total_chunks = sum(r["chunk_count"] for r in rows)
        dominant_share = dominant["chunk_count"] / total_chunks if total_chunks else 0.0
        entropy = _topic_entropy([r["chunk_count"] for r in rows])
        summary.append(
            {
                "topic_id": topic_id,
                "total_chunks": total_chunks,
                "dominant_university_id": dominant["university_id"],
                "dominant_university_name": dominant["university_name"],
                "dominant_university_share": round(100 * dominant_share, 1),
                "n_universities": len(rows),
                "entropy": round(entropy, 3),
                "institution_dominance_flag": dominant_share > INSTITUTION_DOMINANCE_THRESHOLD,
            }
        )
    return summary


def compute_topic_document_type_table(
    topic_chunks: list,
    document_rows: list,
) -> list[dict]:
    """One row per (topic_id, document_type), excluding outlier chunks.

    Reported because document type (institution-wide policy vs. student
    guidance vs. examination guidance vs. teaching-and-learning guidance)
    may explain a topic's content better than country or university does
    -- e.g. a topic dominated by "examination guidance" chunks may really
    be an assessment-rules theme that happens to recur across several
    universities' exam-specific documents, independent of which country or
    institution wrote them.
    """
    doc_meta = _document_metadata_index(document_rows)

    topic_totals: Counter = Counter()
    pair_counts: Counter = Counter()

    for chunk in topic_chunks:
        if chunk.topic_id is None or chunk.topic_id == -1:
            continue
        meta = doc_meta.get(chunk.document_id)
        if meta is None:
            continue
        document_type = meta["document_type"]
        topic_totals[chunk.topic_id] += 1
        pair_counts[(chunk.topic_id, document_type)] += 1

    rows = []
    for (topic_id, document_type), count in sorted(pair_counts.items()):
        topic_total = topic_totals[topic_id]
        rows.append(
            {
                "topic_id": topic_id,
                "document_type": document_type,
                "chunk_count": count,
                "pct_of_topic": round(100 * count / topic_total, 1) if topic_total else 0.0,
            }
        )
    return rows
