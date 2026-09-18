"""Methodology & Limitations page: renders docs/methodology.md and docs/limitations.md
directly, so the dashboard's explanation and the repository's written docs
never drift apart (one source of truth, two presentations).
"""

# ruff: noqa: E402

from __future__ import annotations

from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]

st.set_page_config(page_title="Methodology & Limitations | Nordic AI Policy Tracker", layout="wide")
st.title("Methodology & Limitations")

tab1, tab2, tab3 = st.tabs(["Methodology", "Limitations", "Ethics"])

with tab1:
    methodology_path = REPO_ROOT / "docs" / "methodology.md"
    if methodology_path.exists():
        st.markdown(methodology_path.read_text(encoding="utf-8"))
    else:
        st.error("docs/methodology.md not found.")

with tab2:
    limitations_path = REPO_ROOT / "docs" / "limitations.md"
    if limitations_path.exists():
        st.markdown(limitations_path.read_text(encoding="utf-8"))
    else:
        st.error("docs/limitations.md not found.")

with tab3:
    ethics_path = REPO_ROOT / "docs" / "ethics.md"
    if ethics_path.exists():
        st.markdown(ethics_path.read_text(encoding="utf-8"))
    else:
        st.error("docs/ethics.md not found.")
