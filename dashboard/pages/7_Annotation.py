"""Annotation page: the human-coding interface for the pilot's sole coder.

Walks through each successfully-collected document, one dimension at a
time, showing the document's cleaned text alongside the coding guide's
definition for that dimension, and a form to record a 0-2 score plus
evidence passage, uncertainty flag/note, and coding round.

Saved rows go to data/annotations/annotation_template.csv (upsert by
document_id + dimension_id + coding_round -- an existing row for the same
key is updated in place, not silently duplicated or blindly overwritten:
the previous value is shown before you confirm the change).

This interface produces coder_type="human" rows once used. It does not
pre-fill or suggest scores from the rule-based layer, to avoid anchoring
the human coder's independent judgment -- though the rule-based
candidate-evidence sentences ARE shown as a research aid, clearly labeled
as unvalidated hints, consistent with docs/coding_guide.md.
"""

# ruff: noqa: E402

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))
if str(REPO_ROOT / "dashboard") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "dashboard"))

from components.data_access import load_documents_df, load_settings

from nordic_ai_policy_tracker.config import get_coding_dimensions, resolve_path
from nordic_ai_policy_tracker.modeling.indicators import find_candidate_evidence

st.set_page_config(page_title="Annotation | Nordic AI Policy Tracker", layout="wide")
st.title("Human Annotation")
st.caption(
    "This pilot has one human coder. Scores you save here are stored as coder_type='human' "
    "once exported to the annotation CSV and re-run through scripts/calculate_indices.py "
    "--include-human. See docs/coding_guide.md before coding."
)

ANNOTATIONS_PATH = resolve_path("data/annotations/annotation_template.csv")
ANNOTATION_COLUMNS = [
    "document_id",
    "university_id",
    "dimension_id",
    "axis",
    "score",
    "evidence_passage",
    "evidence_start_offset",
    "evidence_end_offset",
    "uncertainty_flag",
    "uncertainty_note",
    "coder_id",
    "coding_timestamp",
    "coding_round",
]


def load_annotations() -> pd.DataFrame:
    if ANNOTATIONS_PATH.exists():
        df = pd.read_csv(ANNOTATIONS_PATH, dtype=str, keep_default_na=False)
        if df.empty and list(df.columns) != ANNOTATION_COLUMNS:
            df = pd.DataFrame(columns=ANNOTATION_COLUMNS)
        return df
    return pd.DataFrame(columns=ANNOTATION_COLUMNS)


def save_annotations(df: pd.DataFrame) -> None:
    ANNOTATIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ANNOTATIONS_PATH, index=False)


documents_df = load_documents_df()
collected_df = documents_df[documents_df["collection_status"] == "collected"]
if collected_df.empty:
    st.error("No successfully collected documents to annotate yet.")
    st.stop()

coding_dimensions = get_coding_dimensions()
settings = load_settings()

col1, col2 = st.columns(2)
with col1:
    doc_name = st.selectbox("Document", collected_df["university_name"].tolist())
with col2:
    coding_round = st.number_input("Coding round", min_value=1, value=1, step=1)

doc_row = collected_df[collected_df["university_name"] == doc_name].iloc[0]
dimension_ids = [d["id"] for d in coding_dimensions["dimensions"]]
dimension = st.selectbox(
    "Dimension",
    dimension_ids,
    format_func=lambda dim_id: next(
        d["label"] for d in coding_dimensions["dimensions"] if d["id"] == dim_id
    ),
)
dim_meta = next(d for d in coding_dimensions["dimensions"] if d["id"] == dimension)

st.subheader(f"{dim_meta['label']}  ({dim_meta['axis']})")

annotations_df = load_annotations()
existing_mask = (
    (annotations_df.get("document_id") == doc_row["document_id"])
    & (annotations_df.get("dimension_id") == dimension)
    & (annotations_df.get("coding_round") == str(coding_round))
)
existing_row = annotations_df[existing_mask]

with st.expander("Document text", expanded=False):
    st.text(doc_row["cleaned_text"])

with st.expander(
    "Rule-based candidate sentences (unvalidated hint, not a suggested score)", expanded=True
):
    candidates = find_candidate_evidence(
        doc_row["cleaned_text"] or "", dimension, dim_meta["keyword_hints"]
    )
    if not candidates:
        st.caption("No keyword matches found for this dimension in this document.")
    for c in candidates:
        flag = "⚠️ negated/hedged" if c.polarity == "negative_or_hedged" else "plain match"
        st.write(f'- ({flag}) "{c.sentence}"')

st.markdown("---")
st.subheader("Your coding decision")

default_score = (
    int(existing_row.iloc[0]["score"])
    if not existing_row.empty and existing_row.iloc[0]["score"]
    else 0
)
default_evidence = existing_row.iloc[0]["evidence_passage"] if not existing_row.empty else ""
default_uncertainty = (
    existing_row.iloc[0]["uncertainty_flag"].lower() == "true" if not existing_row.empty else False
)
default_note = existing_row.iloc[0]["uncertainty_note"] if not existing_row.empty else ""

if not existing_row.empty:
    st.info(
        f"An existing score for this document/dimension/round is on file: "
        f"score={existing_row.iloc[0]['score']}. Saving below will UPDATE it (shown for confirmation, "
        "never overwritten silently)."
    )

with st.form("annotation_form"):
    score = st.radio("Score", options=[0, 1, 2], index=default_score, horizontal=True)
    evidence = st.text_area(
        "Evidence passage (verbatim quote; required if score > 0)", value=default_evidence
    )
    uncertainty_flag = st.checkbox("Uncertainty flag", value=default_uncertainty)
    uncertainty_note = st.text_area("Uncertainty note (optional)", value=default_note)
    coder_id = st.text_input("Coder ID", value="patricia")
    submitted = st.form_submit_button("Save score")

if submitted:
    if score > 0 and not evidence.strip():
        st.error("A score of 1 or 2 requires an evidence passage. Not saved.")
    else:
        new_row = {
            "document_id": doc_row["document_id"],
            "university_id": doc_row["university_id"],
            "dimension_id": dimension,
            "axis": dim_meta["axis"],
            "score": str(score),
            "evidence_passage": evidence.strip() if score > 0 else "",
            "evidence_start_offset": "",
            "evidence_end_offset": "",
            "uncertainty_flag": str(uncertainty_flag),
            "uncertainty_note": uncertainty_note.strip(),
            "coder_id": coder_id.strip() or "unknown",
            "coding_timestamp": datetime.now(UTC).isoformat(),
            "coding_round": str(coding_round),
        }
        annotations_df = annotations_df[~existing_mask]
        annotations_df = pd.concat([annotations_df, pd.DataFrame([new_row])], ignore_index=True)
        save_annotations(annotations_df)
        st.success(
            "Saved. Run `python scripts/calculate_indices.py --include-human` to recompute "
            "REI/PISI including this score."
        )

st.markdown("---")
st.subheader("Coding progress for this document")
doc_annotations = annotations_df[
    (annotations_df.get("document_id") == doc_row["document_id"])
    & (annotations_df.get("coding_round") == str(coding_round))
]
coded_dims = set(doc_annotations["dimension_id"]) if not doc_annotations.empty else set()
progress_df = pd.DataFrame(
    {
        "dimension": dimension_ids,
        "coded": ["yes" if d in coded_dims else "not yet coded" for d in dimension_ids],
    }
)
st.dataframe(progress_df, width="stretch", hide_index=True)
st.caption(
    f"{len(coded_dims)}/{len(dimension_ids)} dimensions coded for this document in round {coding_round}."
)
