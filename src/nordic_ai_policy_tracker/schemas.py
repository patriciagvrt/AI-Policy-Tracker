"""Pydantic data models (schemas) for the project.

Why pydantic: it validates data as it comes in (e.g. it will refuse to
create a PolicyDocument with a score outside 0-2, or a country not in our
enum) and gives clear error messages when something is wrong, instead of
letting a bad value silently flow through the pipeline and corrupt a
downstream chart. Every table this project writes to SQLite or Parquet is
defined here first as a pydantic model.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field, HttpUrl, field_validator


class NordicCountry(str, Enum):
    SWEDEN = "Sweden"
    NORWAY = "Norway"
    DENMARK = "Denmark"
    FINLAND = "Finland"
    ICELAND = "Iceland"


class CollectionStatus(str, Enum):
    PENDING = "pending"
    COLLECTED = "collected"
    UNCHANGED = "unchanged"  # re-collected, hash matched previous version
    FAILED = "failed"
    SKIPPED_NOT_VERIFIED = "skipped_not_verified"
    SKIPPED_ROBOTS_DISALLOWED = "skipped_robots_disallowed"


class ExtractionMethod(str, Enum):
    HTML_HTTP = "html_http"
    PDF_HTTP = "pdf_http"
    SELENIUM = "selenium"
    NOT_APPLICABLE = "not_applicable"


class TranslationStatus(str, Enum):
    ORIGINAL = "original"
    OFFICIAL_TRANSLATION = "official_translation"
    UNKNOWN = "unknown"


class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    FAILED = "failed"


class LegalReviewStatus(str, Enum):
    """Whether a human has reviewed a source's terms of use / copyright
    posture. This is never inferred automatically -- robots.txt tells the
    collector what it may fetch, but it says nothing about redistribution
    or text-and-data-mining rights, which require a human legal read.
    """

    PENDING = "pending"  # not yet reviewed -- the safe default
    REVIEWED_REDISTRIBUTION_ALLOWED = "reviewed_redistribution_allowed"
    REVIEWED_REDISTRIBUTION_RESTRICTED = "reviewed_redistribution_restricted"
    RESTRICTED = "restricted"  # collection itself should not proceed


# ---------------------------------------------------------------------------
# University registry (mirrors config/universities.csv)
# ---------------------------------------------------------------------------


class University(BaseModel):
    university_id: str
    university_name: str
    country: NordicCountry
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    institution_type: str | None = None
    size_category: str | None = None
    technical_or_comprehensive: str | None = None
    policy_title: str
    policy_url: HttpUrl
    document_type: str
    intended_audience: str
    policy_level: str | None = None
    expected_language: str | None = "en"
    original_language: str | None = None
    collection_method: ExtractionMethod = ExtractionMethod.HTML_HTTP
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    active: bool = False
    selection_status: str | None = None
    selection_rationale: str | None = None
    exclusion_rationale: str | None = None
    notes: str | None = None

    # --- Legal / text-and-data-mining safeguards (source-registry level) ---
    terms_checked: bool = False  # has a human checked this site's terms of use?
    terms_url: str | None = None
    legal_review_status: LegalReviewStatus = LegalReviewStatus.PENDING

    def is_collectable(self) -> bool:
        """A source may only be scraped if it is both active and verified.

        This is the single gate the collector checks before requesting a
        URL -- see collection/crawler.py: read_active_verified_sources().
        """
        return self.active and self.verification_status == VerificationStatus.VERIFIED


# ---------------------------------------------------------------------------
# Policy document (one row per collected document)
# ---------------------------------------------------------------------------


class PolicyDocument(BaseModel):
    document_id: str
    university_id: str
    university_name: str
    country: NordicCountry

    title: str
    source_url: HttpUrl
    canonical_url: str | None = None

    publication_date: date | None = None
    last_updated_date: date | None = None
    retrieval_timestamp: datetime

    # Language protocol fields (Nordic-specific requirement, section 5)
    original_language: str | None = None  # None/unknown allowed -- never guessed
    analyzed_language: str = "en"
    is_official_translation: bool | None = None  # None = unknown
    translation_status: TranslationStatus = TranslationStatus.UNKNOWN
    local_language_url: str | None = None
    english_version_url: str | None = None
    other_language_documents_may_exist: bool | None = None
    language_scope_note: str | None = None

    document_type: str
    intended_audience: str
    policy_level: str | None = None

    file_format: str  # "html" | "pdf"
    http_status: int | None = None
    robots_allowed: bool | None = None
    extraction_method: ExtractionMethod

    raw_text: str = ""
    cleaned_text: str = ""
    text_hash: str | None = None
    word_count: int = 0
    duplicate_of: str | None = None

    collection_status: CollectionStatus = CollectionStatus.PENDING
    error_message: str | None = None
    manual_verification_status: str | None = None

    redistribution_allowed: bool | None = None
    license_note: str | None = None

    # --- Legal / text-and-data-mining safeguards (document level) ---
    terms_checked: bool = False
    terms_url: str | None = None
    copyright_notice: str | None = None  # verbatim copyright line found on the source, if any
    tdm_reservation_detected: bool | None = None  # None = not checked; see collection/robots.py
    legal_review_status: LegalReviewStatus = LegalReviewStatus.PENDING

    @field_validator("word_count")
    @classmethod
    def word_count_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("word_count cannot be negative")
        return v


# ---------------------------------------------------------------------------
# Human / rule-based coding
# ---------------------------------------------------------------------------


class CoderType(str, Enum):
    HUMAN = "human"
    RULE_BASED = "rule_based"


class DimensionScore(BaseModel):
    """One (document, dimension) coding decision.

    This is the long-format table described in Phase 1: one row per
    dimension per document per coding round, rather than wide columns, so
    adding a dimension or a second coder later never requires a schema
    migration.
    """

    document_id: str
    dimension_id: str
    axis: str  # "restriction_enforcement" | "pedagogical_support"
    score: int = Field(ge=0, le=2)
    evidence_passage: str | None = None
    evidence_start_offset: int | None = None
    evidence_end_offset: int | None = None
    uncertainty_flag: bool = False
    uncertainty_note: str | None = None
    coder_id: str
    coder_type: CoderType
    coding_timestamp: datetime
    coding_round: int = 1

    @field_validator("evidence_passage")
    @classmethod
    def evidence_required_for_nonzero_score(cls, v: str | None, info) -> str | None:
        score = info.data.get("score")
        if score is not None and score > 0 and not v:
            raise ValueError(
                "A score of 1 or 2 must be accompanied by an evidence_passage. "
                "This is a hard rule from the project's coding guide."
            )
        return v


# ---------------------------------------------------------------------------
# Indices (REI / PISI)
# ---------------------------------------------------------------------------


class IndexKind(str, Enum):
    """What KIND of index value this is -- never just "REI" or "PISI".

    This distinction is load-bearing, not cosmetic: an automated hint and a
    human-validated score answer different questions, and this project
    never lets one be mistaken for the other, including at the data level
    (not just in a dashboard label). See modeling/indices.py.

    - AUTOMATED_*_HINT: an exploratory, rule-based suggestion. Computed
      even from partial dimension coverage. Never presented as the
      researcher's own interpretation.
    - HUMAN_*: computed ONLY from a human coder's COMPLETE annotation of
      every dimension in that axis for that document (n_coded == n_total).
      If coding is incomplete, no HUMAN_* row is produced at all -- the
      dashboard shows "Not yet human-coded" rather than a partial number.
    - VALIDATED_*: a HUMAN_* result that has additionally passed a
      validation step (currently: a completed round-2/intra-coder
      recoding; later: inter-coder agreement with a second coder). Until a
      validation pass has actually happened, no VALIDATED_* row exists.
    """

    AUTOMATED_REI_HINT = "automated_rei_hint"
    AUTOMATED_PISI_HINT = "automated_pisi_hint"
    HUMAN_REI = "human_rei"
    HUMAN_PISI = "human_pisi"
    VALIDATED_REI = "validated_rei"
    VALIDATED_PISI = "validated_pisi"


class IndexResult(BaseModel):
    """Result of computing one index KIND (see IndexKind) for one document.

    Deliberately keeps the REI-axis and PISI-axis results as two separate
    IndexResult objects, at every kind level (automated / human /
    validated) rather than combining them into one score -- see
    modeling/indices.py.
    """

    document_id: str
    index_name: IndexKind
    raw_score: float  # sum of component scores (before normalization)
    normalized_score: float = Field(ge=0, le=100)
    n_dimensions_total: int
    n_dimensions_coded: int
    n_dimensions_missing: int
    component_scores: dict[str, int]  # dimension_id -> 0/1/2, only coded ones
    weighting_scheme: str = "equal"
    confidence: float = Field(ge=0, le=1)  # n_coded / n_total
    coder_type: CoderType
    coding_round: int = (
        1  # which round of human coding produced this (validated indices reference the latest round)
    )


# ---------------------------------------------------------------------------
# BERTopic exports
# ---------------------------------------------------------------------------


class TopicChunk(BaseModel):
    chunk_id: str
    document_id: str
    university_id: str
    chunk_index: int
    chunk_text: str
    topic_id: int | None = None
    topic_probability: float | None = None
    is_outlier: bool = False


class ManualLabelStatus(str, Enum):
    """Where a topic's MANUAL (researcher-authored) label stands.

    This is never conflated with the automatic label: a topic can carry
    both an `automatic_topic_label` (BERTopic's own c-TF-IDF keyword
    label, always present once a model has run) and a `manual_topic_label`
    (a researcher's interpretation of what the topic is actually about),
    and the two are stored in separate fields precisely so a dashboard or
    report can never silently substitute one for the other.
    """

    UNLABELED = "unlabeled"  # no researcher label has been proposed yet
    PROVISIONAL = "provisional"  # a researcher has proposed a label, not yet confirmed
    CONFIRMED = "confirmed"  # the researcher has reviewed and confirmed this label


class TopicLabel(BaseModel):
    """One topic's automatic and manual labels, kept as separate fields.

    Persisted to data/processed/topic_labels.parquet by
    scripts/train_topics.py. A `manual_topic_label` here is always a
    researcher's own interpretation -- this project never generates one
    automatically and writes it into this field as if a person had
    proposed it.
    """

    topic_id: int
    automatic_topic_label: str  # BERTopic's own keyword-based label, e.g. "ai_disclosure_use"
    top_keywords: list[str] = []
    chunk_count: int = 0
    manual_topic_label: str | None = None
    manual_label_status: ManualLabelStatus = ManualLabelStatus.UNLABELED
    manual_label_note: str | None = None
