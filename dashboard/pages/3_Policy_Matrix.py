"""Policy Matrix page: the REI x PISI scatter plot -- the core visualization.

Compliance note: this page defaults to the HUMAN-CODED view. If no
human-coded data exists at all, it shows an EMPTY plot with an explanatory
message rather than silently falling back to the automated exploratory
hints. A reader who wants the automated hints must explicitly choose that
option from the toggle below -- the two are never blended, and the
automated hints are never presented as if they were the researcher's own
interpretation.
"""

# ruff: noqa: E402

from __future__ import annotations

import json
import sys
from pathlib import Path

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))
if str(REPO_ROOT / "dashboard") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "dashboard"))

from components.data_access import (
    load_automated_hints_df,
    load_documents_df,
    load_human_index_results_df,
    load_validated_index_results_df,
)
from components.labels import (
    AUTOMATED_HINT_DISCLAIMER,
    EMPTY_POLICY_MATRIX_MESSAGE,
    HUMAN_INDEX_DISCLAIMER,
    NO_RANKING_DISCLAIMER,
    PILOT_DISCLAIMER,
    VALIDATED_INDEX_DISCLAIMER,
)
from components.palette import COUNTRY_COLORS

st.set_page_config(page_title="Policy Matrix | Nordic AI Policy Tracker", layout="wide")
st.title("Policy Matrix")
st.warning(PILOT_DISCLAIMER)
st.info(NO_RANKING_DISCLAIMER)

documents_df = load_documents_df()
human_df = load_human_index_results_df()
validated_df = load_validated_index_results_df()
automated_df = load_automated_hints_df()

# --- Build the view options. Human-coded is always first / default. -------
view_options = ["Human-coded indices"]
if not validated_df.empty:
    view_options.append("Validated indices")
view_options.append("Automated exploratory hints")

view = st.radio(
    "Index source",
    options=view_options,
    index=0,  # default: human-coded, per compliance requirement
    horizontal=True,
)

if view == "Human-coded indices":
    working_df = human_df
    st.caption(HUMAN_INDEX_DISCLAIMER)
    rei_key, pisi_key = "human_rei", "human_pisi"
elif view == "Validated indices":
    working_df = validated_df
    st.caption(VALIDATED_INDEX_DISCLAIMER)
    rei_key, pisi_key = "validated_rei", "validated_pisi"
else:
    working_df = automated_df
    st.caption(AUTOMATED_HINT_DISCLAIMER)
    rei_key, pisi_key = "automated_rei_hint", "automated_pisi_hint"

if view == "Human-coded indices" and working_df.empty:
    # The default view with nothing to show: an empty matrix + explanation,
    # never a silent fallback to the automated hints.
    st.warning(EMPTY_POLICY_MATRIX_MESSAGE)
    empty_fig = go.Figure()
    empty_fig.update_xaxes(
        range=[-5, 105], title_text="Restriction & Enforcement Index -- human-coded (0-100)"
    )
    empty_fig.update_yaxes(
        range=[-5, 105],
        title_text="Pedagogical Integration & Support Index -- human-coded (0-100)",
    )
    empty_fig.update_layout(height=400)
    st.plotly_chart(empty_fig, width="stretch")
    st.stop()

if working_df.empty:
    st.info(f"No data available yet for '{view}'.")
    st.stop()

pivot = working_df.pivot_table(
    index="document_id", columns="index_name", values="normalized_score"
).reset_index()
confidence = working_df.pivot_table(
    index="document_id", columns="index_name", values="confidence"
).reset_index()
confidence.columns = ["document_id"] + [f"{c}_confidence" for c in confidence.columns[1:]]
pivot = pivot.merge(confidence, on="document_id", how="left")
pivot = pivot.merge(
    documents_df[
        ["document_id", "university_name", "country", "document_type", "word_count", "source_url"]
    ],
    on="document_id",
    how="left",
)

if rei_key not in pivot.columns or pisi_key not in pivot.columns:
    st.warning(
        f"Both {rei_key} and {pisi_key} need at least one document with a value to plot the matrix."
    )
    st.stop()

pivot[f"{rei_key}_confidence"] = pivot.get(f"{rei_key}_confidence", 0).fillna(0)
pivot[f"{pisi_key}_confidence"] = pivot.get(f"{pisi_key}_confidence", 0).fillna(0)
pivot["avg_confidence"] = (pivot[f"{rei_key}_confidence"] + pivot[f"{pisi_key}_confidence"]) / 2

fig = px.scatter(
    pivot,
    x=rei_key,
    y=pisi_key,
    color="country",
    size="word_count",
    size_max=40,
    color_discrete_map=COUNTRY_COLORS,
    hover_name="university_name",
    hover_data={
        rei_key: ":.1f",
        pisi_key: ":.1f",
        f"{rei_key}_confidence": ":.2f",
        f"{pisi_key}_confidence": ":.2f",
        "document_type": True,
        "word_count": True,
        "country": False,
    },
    labels={
        rei_key: f"Restriction & Enforcement Index ({view}, 0-100)",
        pisi_key: f"Pedagogical Integration & Support Index ({view}, 0-100)",
    },
)
fig.update_xaxes(range=[-5, 105])
fig.update_yaxes(range=[-5, 105])
fig.add_vline(x=50, line_dash="dot", line_color="#B0B0B0")
fig.add_hline(y=50, line_dash="dot", line_color="#B0B0B0")
fig.update_layout(height=600, legend_title_text="Country")

st.plotly_chart(fig, width="stretch")

st.caption(
    "Marker size reflects document word count (a very short document's score carries "
    "more uncertainty). Dotted lines mark the midpoint of each axis purely for visual "
    "reference, not a meaningful threshold."
)

st.subheader("Component scores")
for _, row in pivot.iterrows():
    with st.expander(
        f"{row['university_name']} ({row['country']}) -- source: {row['document_type']}"
    ):
        doc_scores = working_df[working_df["document_id"] == row["document_id"]]
        for _, idx_row in doc_scores.iterrows():
            components = json.loads(idx_row["component_scores_json"])
            st.write(
                f"**{idx_row['index_name']}**: {idx_row['normalized_score']:.1f}/100 "
                f"(confidence {idx_row['confidence']:.2f}, "
                f"{idx_row['n_dimensions_coded']}/{idx_row['n_dimensions_total']} dimensions coded)"
            )
            if components:
                st.json(components)
            else:
                st.caption("No coded components.")
        st.markdown(f"[Source document]({row['source_url']})")
