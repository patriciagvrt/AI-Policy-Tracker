"""Document Comparison page: pick 2+ documents and compare them side by side."""

# ruff: noqa: E402

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))
if str(REPO_ROOT / "dashboard") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "dashboard"))

from components.data_access import (
    has_human_coding,
    load_dimension_scores_df,
    load_documents_df,
    load_human_index_results_df,
    load_topic_assignments_df,
)
from components.labels import AUTOMATED_HINT_DISCLAIMER, HUMAN_INDEX_DISCLAIMER, PILOT_DISCLAIMER

st.set_page_config(page_title="Document Comparison | Nordic AI Policy Tracker", layout="wide")
st.title("Document Comparison")
st.warning(PILOT_DISCLAIMER)

documents_df = load_documents_df()
collected_df = documents_df[documents_df["collection_status"] == "collected"]

if len(collected_df) < 2:
    st.info("Need at least two successfully collected documents to compare.")
    st.stop()

selected_names = st.multiselect(
    "Select two or more documents to compare",
    options=collected_df["university_name"].tolist(),
    default=collected_df["university_name"].tolist()[:2],
)

if len(selected_names) < 2:
    st.info("Select at least two documents.")
    st.stop()

selected_df = collected_df[collected_df["university_name"].isin(selected_names)]

st.subheader("Metadata")
meta_cols = [
    "university_name",
    "country",
    "document_type",
    "intended_audience",
    "policy_level",
    "publication_date",
    "last_updated_date",
    "word_count",
    "source_url",
]
st.dataframe(selected_df[meta_cols].set_index("university_name").T, width="stretch")

human_index_df = load_human_index_results_df()
coder_type = "human" if has_human_coding(human_index_df) else "rule_based"
if coder_type == "human":
    st.caption(HUMAN_INDEX_DISCLAIMER)
else:
    st.caption(AUTOMATED_HINT_DISCLAIMER)

st.subheader(f"Index components ({coder_type})")
dimension_scores_df = load_dimension_scores_df()
scores_for_selected = dimension_scores_df[
    dimension_scores_df["document_id"].isin(selected_df["document_id"])
    & (dimension_scores_df["coder_type"] == coder_type)
]

if scores_for_selected.empty:
    st.info(f"No {coder_type} dimension scores available for the selected documents yet.")
else:
    doc_id_to_name = dict(
        zip(selected_df["document_id"], selected_df["university_name"], strict=False)
    )
    scores_for_selected = scores_for_selected.copy()
    scores_for_selected["university_name"] = scores_for_selected["document_id"].map(doc_id_to_name)
    scores_for_selected["score"] = pd.to_numeric(scores_for_selected["score"], errors="coerce")
    pivot = scores_for_selected.pivot_table(
        index="dimension_id", columns="university_name", values="score"
    )
    pivot = pivot.astype("float64")
    st.dataframe(pivot, width="stretch")

    st.subheader("Evidence passages")
    for _, row in scores_for_selected.iterrows():
        if row["score"] > 0 and row["evidence_passage"]:
            with st.expander(
                f"{row['university_name']} -- {row['dimension_id']} (score {row['score']})"
            ):
                st.write(f"> {row['evidence_passage']}")
                if row["uncertainty_flag"]:
                    st.caption(f"Uncertainty noted: {row['uncertainty_note']}")

st.subheader("Topic prevalence")
topic_assignments_df = load_topic_assignments_df()
if topic_assignments_df.empty:
    st.info("No topic assignments available yet -- run scripts/train_topics.py.")
else:
    merged = topic_assignments_df.merge(
        documents_df[["university_id", "university_name"]], on="university_id", how="left"
    )
    merged = merged[merged["university_name"].isin(selected_names)]
    if merged.empty:
        st.info("No topic-assigned chunks for the selected documents.")
    else:
        prevalence = pd.crosstab(merged["university_name"], merged["topic_id"])
        st.dataframe(prevalence, width="stretch")

st.subheader("Source links")
for _, row in selected_df.iterrows():
    st.markdown(f"- [{row['university_name']}: {row['title']}]({row['source_url']})")
