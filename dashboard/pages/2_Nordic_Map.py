"""Nordic Map page: the five pilot universities plotted geographically."""

# ruff: noqa: E402

from __future__ import annotations

import sys
from pathlib import Path

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
    load_universities_df,
)
from components.labels import PILOT_DISCLAIMER
from components.palette import color_for_country

st.set_page_config(page_title="Nordic Map | Nordic AI Policy Tracker", layout="wide")
st.title("Nordic Map")
st.warning(PILOT_DISCLAIMER)
st.caption(
    "These five points are the pilot's sample, not a census of Nordic universities. "
    "Their placement reflects which institutions had a substantive, publicly "
    "accessible generative-AI policy in English at the time of collection -- see "
    "docs/limitations.md (public-document availability bias). A pilot institution "
    "can appear here even when its document collection failed -- see the "
    "'Analytical status' column below; Lund University is shown as a selected pilot "
    "institution with analytical status 'collection pending', never as analyzed."
)

universities_df = load_universities_df()
documents_df = load_documents_df()
automated_hints_df = load_automated_hints_df()

pilot_df = universities_df[universities_df["selection_status"] == "pilot_selected"].copy()

# Analytical status per university: reflects the actual collection_status of
# its document, never assumed. A university with no COLLECTED document (e.g.
# Lund, whose PDF collection failed) is always "collection pending" here,
# never silently treated as analyzed.
status_lookup: dict[str, str] = {}
if not documents_df.empty:
    for _, drow in documents_df.iterrows():
        status_lookup[drow["university_id"]] = (
            "analyzed" if drow["collection_status"] == "collected" else "collection pending"
        )


def analytical_status(university_id: str) -> str:
    return status_lookup.get(university_id, "collection pending")


# Attach automated_rei_hint/automated_pisi_hint (if available) per university
# for the tooltip. These are exploratory rule-based hints, never presented as
# a human-validated score -- see components/labels.py.
rei_lookup: dict[str, float] = {}
pisi_lookup: dict[str, float] = {}
if not automated_hints_df.empty and not documents_df.empty:
    merged = automated_hints_df.merge(
        documents_df[["document_id", "university_id"]], on="document_id", how="left"
    )
    for _, row in merged.iterrows():
        if row["index_name"] == "automated_rei_hint":
            rei_lookup[row["university_id"]] = row["normalized_score"]
        elif row["index_name"] == "automated_pisi_hint":
            pisi_lookup[row["university_id"]] = row["normalized_score"]

fig = go.Figure()
for country in pilot_df["country"].unique():
    subset = pilot_df[pilot_df["country"] == country]
    hover_text = []
    for _, row in subset.iterrows():
        status = analytical_status(row["university_id"])
        rei = rei_lookup.get(row["university_id"])
        pisi = pisi_lookup.get(row["university_id"])
        rei_str = f"{rei:.1f}" if rei is not None else "not available"
        pisi_str = f"{pisi:.1f}" if pisi is not None else "not available"
        hover_text.append(
            f"<b>{row['university_name']}</b><br>"
            f"{row['policy_title']}<br>"
            f"Document type: {row['document_type']}<br>"
            f"Analytical status: {status}<br>"
            f"automated_rei_hint: {rei_str}<br>"
            f"automated_pisi_hint: {pisi_str}"
        )
    fig.add_trace(
        go.Scattergeo(
            lon=subset["longitude"],
            lat=subset["latitude"],
            text=hover_text,
            hoverinfo="text",
            mode="markers",
            marker=dict(
                size=14, color=color_for_country(country), line=dict(width=1, color="white")
            ),
            name=country,
        )
    )

fig.update_geos(
    scope="europe",
    center={"lat": 62, "lon": 15},
    projection_scale=3.2,
    showland=True,
    landcolor="#EDEDED",
    showcountries=True,
    countrycolor="#B0B0B0",
)
fig.update_layout(
    height=650,
    margin=dict(l=0, r=0, t=20, b=0),
    legend_title_text="Country",
)

st.plotly_chart(fig, width="stretch")

st.subheader("Pilot universities")
pilot_df["analytical_status"] = pilot_df["university_id"].map(analytical_status)
display_cols = [
    "university_name",
    "country",
    "city",
    "policy_title",
    "document_type",
    "intended_audience",
    "analytical_status",
    "policy_url",
]
st.dataframe(pilot_df[display_cols], width="stretch", hide_index=True)
