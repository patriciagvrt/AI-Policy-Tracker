"""Overview page: collection status, coverage, missing-data warnings."""

# ruff: noqa: E402

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))
if str(REPO_ROOT / "dashboard") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "dashboard"))

from components.data_access import load_collection_audit_df, load_documents_df
from components.labels import PILOT_DISCLAIMER

st.set_page_config(page_title="Overview | Nordic AI Policy Tracker", layout="wide")
st.title("Overview")
st.warning(PILOT_DISCLAIMER)

documents_df = load_documents_df()

if documents_df.empty:
    st.error("No documents in the database yet. Run the collection pipeline first.")
    st.stop()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Universities tracked", documents_df["university_id"].nunique())
col2.metric("Documents", len(documents_df))
col3.metric("Countries", documents_df["country"].nunique())
col4.metric(
    "Collected successfully",
    int((documents_df["collection_status"] == "collected").sum()),
)

st.subheader("Document types and audiences")
c1, c2 = st.columns(2)
with c1:
    st.write("**Document type**")
    st.dataframe(documents_df["document_type"].value_counts().rename("count"))
with c2:
    st.write("**Intended audience**")
    st.dataframe(documents_df["intended_audience"].value_counts().rename("count"))

st.subheader("Language status")
lang_cols = [
    "university_name",
    "original_language",
    "analyzed_language",
    "is_official_translation",
    "translation_status",
    "other_language_documents_may_exist",
]
st.dataframe(documents_df[lang_cols], width="stretch")
st.caption(
    "`original_language` and `is_official_translation` are left blank/unknown where this "
    "could not be confirmed from the source page -- see docs/limitations.md "
    "(official-translation uncertainty). This is never guessed."
)

st.subheader("Retrieval dates")
st.dataframe(
    documents_df[["university_name", "retrieval_timestamp", "http_status", "collection_status"]],
    width="stretch",
)

st.subheader("Legal / text-and-data-mining review status")
legal_cols = [
    c
    for c in [
        "university_name",
        "robots_allowed",
        "terms_checked",
        "legal_review_status",
        "redistribution_allowed",
    ]
    if c in documents_df.columns
]
st.dataframe(documents_df[legal_cols], width="stretch")
st.caption(
    "`terms_checked`/`legal_review_status` default to unchecked/pending -- this project does not "
    "infer redistribution rights automatically. See `docs/legal_and_compliance.md`."
)

st.subheader("Missing-data warnings")
warnings = []
for _, row in documents_df.iterrows():
    if row["collection_status"] != "collected":
        warnings.append(
            f"- **{row['university_name']}**: collection status = `{row['collection_status']}`"
            f"{' -- ' + row['error_message'] if row.get('error_message') else ''}"
        )
    elif row.get("word_count", 0) and row["word_count"] < 100:
        warnings.append(
            f"- **{row['university_name']}**: unusually short document ({row['word_count']} words)"
        )
    if not row.get("original_language"):
        warnings.append(f"- **{row['university_name']}**: original_language unknown")

if warnings:
    st.markdown("\n".join(sorted(set(warnings))))
else:
    st.success("No missing-data warnings.")

st.subheader("Collection audit log")
audit_df = load_collection_audit_df()
if audit_df.empty:
    st.info("No collection audit entries recorded yet.")
else:
    st.dataframe(audit_df, width="stretch")
