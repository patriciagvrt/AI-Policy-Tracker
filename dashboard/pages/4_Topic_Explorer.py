"""Topic Explorer page: BERTopic output, explicitly labeled experimental."""

# ruff: noqa: E402

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))
if str(REPO_ROOT / "dashboard") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "dashboard"))

from components.data_access import (
    load_chunks_df,
    load_documents_df,
    load_topic_assignments_df,
    load_topic_labels_df,
)
from components.labels import BERTOPIC_DISCLAIMER, PILOT_DISCLAIMER

from nordic_ai_policy_tracker.modeling.topic_diagnostics import (  # noqa: E402
    INSTITUTION_DOMINANCE_THRESHOLD,
    compute_institution_dominance,
    compute_topic_document_type_table,
    compute_topic_university_table,
)
from nordic_ai_policy_tracker.schemas import TopicChunk  # noqa: E402

st.set_page_config(page_title="Topic Explorer | Nordic AI Policy Tracker", layout="wide")
st.title("Topic Explorer")
st.warning(PILOT_DISCLAIMER)
st.error(BERTOPIC_DISCLAIMER)

assignments_df = load_topic_assignments_df()
chunks_df = load_chunks_df()
documents_df = load_documents_df()

report_path = REPO_ROOT / "outputs" / "reports" / "topic_model_report.md"
if report_path.exists():
    with st.expander("Full topic model report (parameters, exact wording)", expanded=False):
        st.markdown(report_path.read_text(encoding="utf-8"))

if assignments_df.empty:
    st.info(
        "No topic assignments available. Either `python scripts/train_topics.py` has not been "
        "run yet, or it refused to fit a model because the corpus was too small (see the report "
        "above, or docs/limitations.md)."
    )
    st.stop()

merged = assignments_df.merge(chunks_df[["chunk_id", "chunk_text"]], on="chunk_id", how="left")
merged = merged.merge(
    documents_df[["university_id", "university_name", "country"]], on="university_id", how="left"
)

topic_labels_df = load_topic_labels_df()

st.subheader("Topic labels: automatic vs. manual")
st.caption(
    "The automatic label comes from BERTopic's own c-TF-IDF keywords. The manual label is a "
    "researcher's interpretation, always shown separately and tagged with its status -- never "
    "merged into a single label, so a provisional or unconfirmed researcher reading is never "
    "presented as the model's own output."
)
if topic_labels_df.empty:
    st.info(
        "No topic_labels.parquet found yet. Run `python scripts/train_topics.py` to generate "
        "automatic labels (and, where proposed, provisional manual labels)."
    )
else:
    display_cols = [
        "topic_id",
        "automatic_topic_label",
        "top_keywords",
        "manual_topic_label",
        "manual_label_status",
        "manual_label_note",
    ]
    st.dataframe(
        topic_labels_df[[c for c in display_cols if c in topic_labels_df.columns]],
        width="stretch",
    )
    if (topic_labels_df["manual_label_status"] == "provisional").any():
        st.warning(
            "One or more manual labels above are `provisional`: proposed by a researcher but "
            "not yet confirmed. Treat them as a working interpretation, not a settled finding."
        )

st.subheader("Topic prevalence by university")
non_outlier = merged[~merged["is_outlier"]]
if non_outlier.empty:
    st.info("Every chunk was assigned as an outlier -- no stable topics to show prevalence for.")
else:
    prevalence = (
        non_outlier.groupby(["university_name", "topic_id"]).size().reset_index(name="chunk_count")
    )
    prevalence["topic_id"] = prevalence["topic_id"].astype(str)
    fig = px.bar(
        prevalence,
        x="university_name",
        y="chunk_count",
        color="topic_id",
        labels={"university_name": "University", "chunk_count": "Chunk count", "topic_id": "Topic"},
    )
    fig.update_layout(height=450)
    st.plotly_chart(fig, width="stretch")

st.subheader("Outlier chunks")
outliers = merged[merged["is_outlier"]]
st.caption(
    f"{len(outliers)} of {len(merged)} chunks were classified as outliers "
    "(did not fit cleanly into any discovered topic)."
)
if not outliers.empty:
    st.dataframe(
        outliers[["university_name", "chunk_text"]].rename(
            columns={"chunk_text": "chunk (outlier)"}
        ),
        width="stretch",
    )

st.subheader("Chunk-level topic assignments")
st.dataframe(
    merged[["university_name", "topic_id", "topic_probability", "is_outlier", "chunk_text"]],
    width="stretch",
)

st.subheader("Institution-dominance diagnostics")
st.caption(
    "An institution-dominated topic (most chunks from one university) may reflect that "
    "source's writing style, document type, or source-specific vocabulary rather than a "
    "general policy theme shared across the corpus. Flag threshold: dominant university "
    f"accounts for more than {int(INSTITUTION_DOMINANCE_THRESHOLD * 100)}% of a topic's chunks."
)

topic_chunk_objs = [
    TopicChunk(
        chunk_id=row["chunk_id"],
        document_id=row["document_id"],
        university_id=row["university_id"],
        chunk_index=int(row["chunk_index"]),
        chunk_text=row.get("chunk_text") or "",
        topic_id=(None if pd.isna(row["topic_id"]) else int(row["topic_id"])),
        is_outlier=bool(row["is_outlier"]),
    )
    for _, row in merged.iterrows()
]
document_rows = documents_df.to_dict(orient="records")

dominance_summary = compute_institution_dominance(topic_chunk_objs, document_rows)
if dominance_summary:
    dominance_df = pd.DataFrame(dominance_summary)
    st.dataframe(dominance_df, width="stretch")
    if dominance_df["institution_dominance_flag"].any():
        st.warning(
            "One or more topics above are flagged as potentially institution-specific -- see "
            "the caption above before treating them as general policy themes."
        )
else:
    st.info("No non-outlier topics to compute institution-dominance diagnostics for.")

with st.expander("Topic-by-university breakdown", expanded=False):
    university_table = compute_topic_university_table(topic_chunk_objs, document_rows)
    if university_table:
        st.dataframe(pd.DataFrame(university_table), width="stretch")
    else:
        st.info("No non-outlier topics to break down by university.")

st.subheader("Document-type diagnostics")
st.caption(
    "Document type (institution-wide policy / student guidance / examination guidance / "
    "teaching-and-learning guidance) may explain a topic's content better than country or "
    "university does."
)
doc_type_table = compute_topic_document_type_table(topic_chunk_objs, document_rows)
if doc_type_table:
    st.dataframe(pd.DataFrame(doc_type_table), width="stretch")
else:
    st.info("No non-outlier topics to break down by document type.")
