"""SQLite access layer.

Keeps all raw SQL in one place. Every other module talks to the database
through the functions here (save_document, get_document, etc.) rather than
opening its own connection, so the schema only needs to be defined once.

We use plain sqlite3 + hand-written SQL rather than an ORM. For a project
this size (a handful of tables, a few dozen rows in the pilot) an ORM would
add a dependency and a learning curve without much benefit; raw SQL is also
easier for a learner to read and to inspect directly with the `sqlite3`
command-line tool.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

from nordic_ai_policy_tracker.schemas import DimensionScore, IndexKind, IndexResult, PolicyDocument

# --- Compliance note on automated vs. human vs. validated index storage ---
#
# The project's compliance correction requires that automated (rule-based)
# suggestions and human-coded indices be "preserve[d]... in separate
# database tables or clearly separated fields" -- the user's own wording
# offers both as acceptable. This project uses the "clearly separated
# fields" option rather than three parallel tables: every row's
# `index_name` column can ONLY ever hold one of the six IndexKind enum
# values (automated_rei_hint, automated_pisi_hint, human_rei, human_pisi,
# validated_rei, validated_pisi) -- never a bare "REI"/"PISI" string -- and
# a `index_kind` column additionally records the coarse category
# ("automated_hint" | "human" | "validated") so callers can filter without
# string-parsing index_name. This keeps one queryable table (simpler for a
# single-coder pilot) while making it structurally impossible to write an
# ambiguous row or to accidentally blend an automated hint into a query
# that asked for human results only.
INDEX_KIND_CATEGORY = {
    IndexKind.AUTOMATED_REI_HINT: "automated_hint",
    IndexKind.AUTOMATED_PISI_HINT: "automated_hint",
    IndexKind.HUMAN_REI: "human",
    IndexKind.HUMAN_PISI: "human",
    IndexKind.VALIDATED_REI: "validated",
    IndexKind.VALIDATED_PISI: "validated",
}

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS documents (
    document_id TEXT PRIMARY KEY,
    university_id TEXT NOT NULL,
    university_name TEXT NOT NULL,
    country TEXT NOT NULL,
    title TEXT NOT NULL,
    source_url TEXT NOT NULL,
    canonical_url TEXT,
    publication_date TEXT,
    last_updated_date TEXT,
    retrieval_timestamp TEXT NOT NULL,
    original_language TEXT,
    analyzed_language TEXT NOT NULL,
    is_official_translation INTEGER,
    translation_status TEXT NOT NULL,
    local_language_url TEXT,
    english_version_url TEXT,
    other_language_documents_may_exist INTEGER,
    language_scope_note TEXT,
    document_type TEXT NOT NULL,
    intended_audience TEXT NOT NULL,
    policy_level TEXT,
    file_format TEXT NOT NULL,
    http_status INTEGER,
    robots_allowed INTEGER,
    extraction_method TEXT NOT NULL,
    raw_text TEXT,
    cleaned_text TEXT,
    text_hash TEXT,
    word_count INTEGER NOT NULL DEFAULT 0,
    duplicate_of TEXT,
    collection_status TEXT NOT NULL,
    error_message TEXT,
    manual_verification_status TEXT,
    redistribution_allowed INTEGER,
    license_note TEXT,
    terms_checked INTEGER NOT NULL DEFAULT 0,
    terms_url TEXT,
    copyright_notice TEXT,
    tdm_reservation_detected INTEGER,
    legal_review_status TEXT NOT NULL DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS dimension_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id TEXT NOT NULL,
    dimension_id TEXT NOT NULL,
    axis TEXT NOT NULL,
    score INTEGER NOT NULL,
    evidence_passage TEXT,
    evidence_start_offset INTEGER,
    evidence_end_offset INTEGER,
    uncertainty_flag INTEGER NOT NULL DEFAULT 0,
    uncertainty_note TEXT,
    coder_id TEXT NOT NULL,
    coder_type TEXT NOT NULL,
    coding_timestamp TEXT NOT NULL,
    coding_round INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (document_id) REFERENCES documents(document_id)
);

CREATE TABLE IF NOT EXISTS index_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id TEXT NOT NULL,
    index_name TEXT NOT NULL,      -- one of the six IndexKind values ONLY; never a bare "REI"/"PISI"
    index_kind TEXT NOT NULL,      -- 'automated_hint' | 'human' | 'validated' -- see INDEX_KIND_CATEGORY
    raw_score REAL NOT NULL,
    normalized_score REAL NOT NULL,
    n_dimensions_total INTEGER NOT NULL,
    n_dimensions_coded INTEGER NOT NULL,
    n_dimensions_missing INTEGER NOT NULL,
    component_scores_json TEXT NOT NULL,
    weighting_scheme TEXT NOT NULL,
    confidence REAL NOT NULL,
    coder_type TEXT NOT NULL,
    coding_round INTEGER NOT NULL DEFAULT 1,
    computed_at TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents(document_id)
);

CREATE TABLE IF NOT EXISTS collection_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    university_id TEXT NOT NULL,
    source_url TEXT NOT NULL,
    attempted_at TEXT NOT NULL,
    outcome TEXT NOT NULL,
    http_status INTEGER,
    error_message TEXT,
    retrieval_method TEXT NOT NULL
);
"""


@contextmanager
def get_connection(db_path: str | Path) -> Iterator[sqlite3.Connection]:
    """Yield a SQLite connection with foreign keys enabled, closing it after use."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str | Path) -> None:
    """Create all tables if they don't already exist. Safe to call repeatedly."""
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA_SQL)


def _iso(value: date | datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def save_document(db_path: str | Path, doc: PolicyDocument) -> None:
    """Insert or replace a PolicyDocument row.

    Uses INSERT OR REPLACE keyed on document_id, so re-running the
    collector on the same source updates the existing row rather than
    creating a duplicate.
    """
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO documents (
                document_id, university_id, university_name, country, title,
                source_url, canonical_url, publication_date, last_updated_date,
                retrieval_timestamp, original_language, analyzed_language,
                is_official_translation, translation_status, local_language_url,
                english_version_url, other_language_documents_may_exist,
                language_scope_note, document_type, intended_audience, policy_level,
                file_format, http_status, robots_allowed, extraction_method,
                raw_text, cleaned_text, text_hash, word_count, duplicate_of,
                collection_status, error_message, manual_verification_status,
                redistribution_allowed, license_note,
                terms_checked, terms_url, copyright_notice, tdm_reservation_detected,
                legal_review_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                doc.document_id,
                doc.university_id,
                doc.university_name,
                doc.country.value,
                doc.title,
                str(doc.source_url),
                doc.canonical_url,
                _iso(doc.publication_date),
                _iso(doc.last_updated_date),
                _iso(doc.retrieval_timestamp),
                doc.original_language,
                doc.analyzed_language,
                None if doc.is_official_translation is None else int(doc.is_official_translation),
                doc.translation_status.value,
                doc.local_language_url,
                doc.english_version_url,
                (
                    None
                    if doc.other_language_documents_may_exist is None
                    else int(doc.other_language_documents_may_exist)
                ),
                doc.language_scope_note,
                doc.document_type,
                doc.intended_audience,
                doc.policy_level,
                doc.file_format,
                doc.http_status,
                None if doc.robots_allowed is None else int(doc.robots_allowed),
                doc.extraction_method.value,
                doc.raw_text,
                doc.cleaned_text,
                doc.text_hash,
                doc.word_count,
                doc.duplicate_of,
                doc.collection_status.value,
                doc.error_message,
                doc.manual_verification_status,
                None if doc.redistribution_allowed is None else int(doc.redistribution_allowed),
                doc.license_note,
                int(doc.terms_checked),
                doc.terms_url,
                doc.copyright_notice,
                None if doc.tdm_reservation_detected is None else int(doc.tdm_reservation_detected),
                doc.legal_review_status.value,
            ),
        )


def get_document(db_path: str | Path, document_id: str) -> sqlite3.Row | None:
    with get_connection(db_path) as conn:
        cur = conn.execute("SELECT * FROM documents WHERE document_id = ?", (document_id,))
        return cur.fetchone()


def list_documents(db_path: str | Path) -> list[sqlite3.Row]:
    with get_connection(db_path) as conn:
        cur = conn.execute("SELECT * FROM documents ORDER BY country, university_name")
        return cur.fetchall()


def save_dimension_score(db_path: str | Path, score: DimensionScore) -> None:
    """Insert or replace one DimensionScore row.

    Identity for "replace" purposes is (document_id, dimension_id,
    coder_id, coder_type, coding_round) -- the same (document, dimension)
    coded again by the same coder in the same round is an update to that
    coding decision, not a second, independent one. A different coder_id
    (a second human coder, for inter-coder reliability) or a different
    coding_round (a recoding pass) legitimately gets its own row.

    This was previously a plain INSERT with no such guard, which meant
    re-running scripts/calculate_indices.py (a normal, expected workflow --
    e.g. running the rule-based pass once, then again later with
    --include-human) silently duplicated every dimension_scores row rather
    than updating it. That duplication was confirmed as the root cause of
    the Policy Matrix page showing each automated component score twice:
    the page correctly renders one entry per matching row, but the
    underlying table had two identical rows per (document, dimension).
    """
    with get_connection(db_path) as conn:
        conn.execute(
            """
            DELETE FROM dimension_scores
            WHERE document_id = ? AND dimension_id = ? AND coder_id = ?
              AND coder_type = ? AND coding_round = ?
            """,
            (
                score.document_id,
                score.dimension_id,
                score.coder_id,
                score.coder_type.value,
                score.coding_round,
            ),
        )
        conn.execute(
            """
            INSERT INTO dimension_scores (
                document_id, dimension_id, axis, score, evidence_passage,
                evidence_start_offset, evidence_end_offset, uncertainty_flag,
                uncertainty_note, coder_id, coder_type, coding_timestamp, coding_round
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                score.document_id,
                score.dimension_id,
                score.axis,
                score.score,
                score.evidence_passage,
                score.evidence_start_offset,
                score.evidence_end_offset,
                int(score.uncertainty_flag),
                score.uncertainty_note,
                score.coder_id,
                score.coder_type.value,
                _iso(score.coding_timestamp),
                score.coding_round,
            ),
        )


def list_dimension_scores(
    db_path: str | Path, document_id: str | None = None, coder_type: str | None = None
) -> list[sqlite3.Row]:
    query = "SELECT * FROM dimension_scores WHERE 1=1"
    params: list[str] = []
    if document_id:
        query += " AND document_id = ?"
        params.append(document_id)
    if coder_type:
        query += " AND coder_type = ?"
        params.append(coder_type)
    with get_connection(db_path) as conn:
        cur = conn.execute(query, params)
        return cur.fetchall()


def save_index_result(db_path: str | Path, result: IndexResult) -> None:
    """Insert or replace one IndexResult row.

    result.index_name must be an IndexKind value (automated_rei_hint,
    human_rei, validated_rei, etc.) -- the schema's own typing already
    enforces this before we ever get here. The index_kind column is
    derived from it automatically, so callers never have to keep the two
    in sync by hand.

    Identity for "replace" purposes is (document_id, index_name,
    coder_type, coding_round): recomputing the same index kind for the
    same document/round replaces the prior value rather than adding a
    second row next to it. This was previously a plain INSERT with no
    such guard -- see save_dimension_score()'s docstring for the bug this
    caused (confirmed root cause of the Policy Matrix page's duplicated
    component-score display) and why re-running scripts/calculate_indices.py
    is a normal workflow this needs to tolerate.
    """
    index_kind_value = IndexKind(result.index_name)
    with get_connection(db_path) as conn:
        conn.execute(
            """
            DELETE FROM index_results
            WHERE document_id = ? AND index_name = ? AND coder_type = ? AND coding_round = ?
            """,
            (
                result.document_id,
                index_kind_value.value,
                result.coder_type.value,
                result.coding_round,
            ),
        )
        conn.execute(
            """
            INSERT INTO index_results (
                document_id, index_name, index_kind, raw_score, normalized_score,
                n_dimensions_total, n_dimensions_coded, n_dimensions_missing,
                component_scores_json, weighting_scheme, confidence, coder_type,
                coding_round, computed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.document_id,
                index_kind_value.value,
                INDEX_KIND_CATEGORY[index_kind_value],
                result.raw_score,
                result.normalized_score,
                result.n_dimensions_total,
                result.n_dimensions_coded,
                result.n_dimensions_missing,
                json.dumps(result.component_scores),
                result.weighting_scheme,
                result.confidence,
                result.coder_type.value,
                result.coding_round,
                datetime.utcnow().isoformat(),
            ),
        )


def list_index_results(db_path: str | Path, index_kind: str | None = None) -> list[sqlite3.Row]:
    """List index_results rows, optionally filtered to one category.

    index_kind, if given, must be 'automated_hint', 'human', or 'validated'.
    This is the recommended way for callers (dashboard pages, scripts) to
    read only one kind of result without accidentally blending automated
    hints into a human-only view, or vice versa.
    """
    query = "SELECT * FROM index_results WHERE 1=1"
    params: list[str] = []
    if index_kind:
        query += " AND index_kind = ?"
        params.append(index_kind)
    query += " ORDER BY document_id, index_name"
    with get_connection(db_path) as conn:
        cur = conn.execute(query, params)
        return cur.fetchall()


def log_collection_attempt(
    db_path: str | Path,
    university_id: str,
    source_url: str,
    outcome: str,
    retrieval_method: str,
    http_status: int | None = None,
    error_message: str | None = None,
) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO collection_audit (
                university_id, source_url, attempted_at, outcome,
                http_status, error_message, retrieval_method
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                university_id,
                source_url,
                datetime.utcnow().isoformat(),
                outcome,
                http_status,
                error_message,
                retrieval_method,
            ),
        )


def list_collection_audit(db_path: str | Path) -> list[sqlite3.Row]:
    with get_connection(db_path) as conn:
        cur = conn.execute("SELECT * FROM collection_audit ORDER BY attempted_at DESC")
        return cur.fetchall()
