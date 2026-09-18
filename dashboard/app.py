"""Nordic University AI Policy Tracker -- dashboard entry point.

Run with: streamlit run dashboard/app.py

This file is intentionally thin: it sets page config and shows a landing
page with the pilot disclaimer and navigation. Each actual view lives in
dashboard/pages/ as a separate Streamlit multipage-app page, which is the
standard Streamlit pattern for a multi-page dashboard (files there are
auto-discovered and shown in the sidebar).
"""

# ruff: noqa: E402

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))
if str(REPO_ROOT / "dashboard") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "dashboard"))

from components.data_access import load_documents_df, load_settings
from components.labels import NO_RANKING_DISCLAIMER, PILOT_DISCLAIMER

st.set_page_config(
    page_title="Nordic University AI Policy Tracker",
    page_icon="🇳🇴",
    layout="wide",
)

st.title("Nordic University AI Policy Tracker")
st.caption(
    "Pilot: Lund University · University of Oslo · Aarhus University · Aalto University · Reykjavik University"
)

st.warning(PILOT_DISCLAIMER)
st.info(NO_RANKING_DISCLAIMER)

st.markdown("""
This dashboard examines how five Nordic universities' official generative-AI
guidance documents frame **restriction and enforcement** versus
**pedagogical integration and support** -- as two separate axes, not one
"strict vs. lenient" scale.

Use the sidebar to navigate:

- **Overview** -- collection status, coverage, and data-quality warnings.
- **Nordic Map** -- the five pilot universities, mapped.
- **Policy Matrix** -- the REI x PISI scatter plot.
- **Topic Explorer** -- exploratory BERTopic output (experimental).
- **Document Comparison** -- side-by-side comparison of two or more documents.
- **Methodology & Limitations** -- how this was built, and what it can't tell you.
""")

try:
    settings = load_settings()
    documents_df = load_documents_df()
    n_docs = len(documents_df)
    n_collected = int((documents_df["collection_status"] == "collected").sum()) if n_docs else 0
    col1, col2, col3 = st.columns(3)
    col1.metric("Documents tracked", n_docs)
    col2.metric("Successfully collected", n_collected)
    col3.metric("Countries", documents_df["country"].nunique() if n_docs else 0)
except Exception as exc:  # noqa: BLE001
    st.error(
        "Could not load the database yet. Run the collection pipeline first: "
        "`python scripts/collect_documents.py --sandbox-fixture` (or `--live`), then "
        "`python scripts/process_documents.py` and `python scripts/calculate_indices.py`."
    )
    st.exception(exc)
