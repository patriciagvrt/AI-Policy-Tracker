"""Shared data-loading helpers for every dashboard page.

Centralizing this here means every page reads the same database with the
same caching behavior, and a schema change only needs to be handled in one
place.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from nordic_ai_policy_tracker.config import get_settings, resolve_path  # noqa: E402
from nordic_ai_policy_tracker.database import (  # noqa: E402
    get_connection,
    init_db,
)


@st.cache_data(ttl=60)
def load_settings() -> dict:
    return get_settings()


def get_db_path() -> Path:
    settings = load_settings()
    return resolve_path(settings["paths"]["database_path"])


@st.cache_data(ttl=30)
def load_documents_df() -> pd.DataFrame:
    db_path = get_db_path()
    init_db(db_path)  # safe no-op if tables already exist; guards a fresh clone with no DB yet
    with get_connection(db_path) as conn:
        return pd.read_sql_query("SELECT * FROM documents", conn)


@st.cache_data(ttl=30)
def load_universities_df() -> pd.DataFrame:
    settings = load_settings()
    csv_path = resolve_path(settings["paths"]["universities_csv"])
    return pd.read_csv(csv_path)


@st.cache_data(ttl=30)
def load_index_results_df() -> pd.DataFrame:
    """Loads the FULL index_results table -- automated hints, human results,
    and validated results all together, distinguished by the `index_kind`
    column ('automated_hint' | 'human' | 'validated').

    Most callers should NOT use this directly -- use
    load_automated_hints_df() / load_human_index_results_df() /
    load_validated_index_results_df() below instead, so a page can't
    accidentally blend index kinds by forgetting to filter.
    """
    db_path = get_db_path()
    with get_connection(db_path) as conn:
        return pd.read_sql_query("SELECT * FROM index_results", conn)


def _load_index_results_of_kind(index_kind: str) -> pd.DataFrame:
    df = load_index_results_df()
    if df.empty:
        return df
    return df[df["index_kind"] == index_kind].reset_index(drop=True)


def load_automated_hints_df() -> pd.DataFrame:
    """Rows with index_name in {automated_rei_hint, automated_pisi_hint} only."""
    return _load_index_results_of_kind("automated_hint")


def load_human_index_results_df() -> pd.DataFrame:
    """Rows with index_name in {human_rei, human_pisi} only."""
    return _load_index_results_of_kind("human")


def load_validated_index_results_df() -> pd.DataFrame:
    """Rows with index_name in {validated_rei, validated_pisi} only."""
    return _load_index_results_of_kind("validated")


@st.cache_data(ttl=30)
def load_dimension_scores_df() -> pd.DataFrame:
    db_path = get_db_path()
    with get_connection(db_path) as conn:
        return pd.read_sql_query("SELECT * FROM dimension_scores", conn)


@st.cache_data(ttl=30)
def load_collection_audit_df() -> pd.DataFrame:
    db_path = get_db_path()
    with get_connection(db_path) as conn:
        return pd.read_sql_query("SELECT * FROM collection_audit ORDER BY attempted_at DESC", conn)


@st.cache_data(ttl=30)
def load_chunks_df() -> pd.DataFrame:
    settings = load_settings()
    chunks_path = resolve_path(settings["paths"]["processed_dir"]) / "chunks.parquet"
    if not chunks_path.exists():
        return pd.DataFrame()
    return pd.read_parquet(chunks_path)


@st.cache_data(ttl=30)
def load_topic_assignments_df() -> pd.DataFrame:
    settings = load_settings()
    path = resolve_path(settings["paths"]["processed_dir"]) / "topic_assignments.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


@st.cache_data(ttl=30)
def load_topic_labels_df() -> pd.DataFrame:
    """Loads topic_labels.parquet: one row per topic, with
    automatic_topic_label and manual_topic_label kept as SEPARATE columns
    (plus manual_label_status/manual_label_note) -- never merge these into
    a single "label" column, so the dashboard can never present a
    researcher's provisional interpretation as the model's own output, or
    vice versa. See nordic_ai_policy_tracker.schemas.TopicLabel.
    """
    settings = load_settings()
    path = resolve_path(settings["paths"]["processed_dir"]) / "topic_labels.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def has_human_coding(index_results_df: pd.DataFrame) -> bool:
    """True if the given dataframe (any load_*_df() result) contains at
    least one human-coded index row. Prefer passing the result of
    load_human_index_results_df() here, but this also works against the
    full load_index_results_df() table since it filters on index_kind
    (falling back to coder_type for any legacy rows without that column).
    """
    if index_results_df.empty:
        return False
    if "index_kind" in index_results_df.columns:
        return (index_results_df["index_kind"] == "human").any()
    return (index_results_df["coder_type"] == "human").any()


def has_validated_coding(index_results_df: pd.DataFrame) -> bool:
    if index_results_df.empty:
        return False
    if "index_kind" in index_results_df.columns:
        return (index_results_df["index_kind"] == "validated").any()
    return False
