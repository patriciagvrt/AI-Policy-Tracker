# Data Dictionary

## `config/universities.csv` (source registry)

| Field | Type | Description |
|---|---|---|
| `university_id` | string | Stable short ID, e.g. `lund_se`. Used as a foreign key throughout. |
| `university_name` | string | Full institution name. |
| `country` | enum | One of Sweden, Norway, Denmark, Finland, Iceland. |
| `city` | string | City the institution is based in. |
| `latitude`, `longitude` | float | Approximate coordinates, used by the Nordic Map dashboard page. |
| `institution_type` | string | e.g. comprehensive, technical. |
| `size_category` | string | e.g. small/medium/large (by stated student population). |
| `technical_or_comprehensive` | string | Orientation descriptor for stratified-sampling purposes. |
| `policy_title` | string | Title of the source document as published. |
| `policy_url` | URL | Source URL. |
| `document_type` | string | e.g. institution-wide policy, student guidance. |
| `intended_audience` | string | e.g. students; staff and students; teachers and students. |
| `policy_level` | string | e.g. institution-wide. |
| `expected_language` | string | Language the source is expected to be in (`en` for the pilot). |
| `original_language` | string, nullable | Left blank when unconfirmed -- never guessed. |
| `collection_method` | enum | `html_http`, `pdf_http`, `selenium`, or `not_applicable`. |
| `verification_status` | enum | `verified`, `unverified`, or `failed`. Gates collection. |
| `active` | bool | Gates collection. Both `active=true` and `verification_status=verified` are required to be scraped. |
| `selection_status` | string | e.g. `pilot_selected`, `candidate_not_selected`, `candidate_needs_verification`. |
| `selection_rationale` | string | Why this source was (or wasn't) selected. |
| `exclusion_rationale` | string | Why a candidate was excluded, if applicable. |
| `notes` | string | Free-text notes, including known caveats. |

## `documents` table (SQLite, `data/processed/policy_tracker.db`)

| Field | Type | Description |
|---|---|---|
| `document_id` | string (PK) | Deterministic hash of `(university_id, source_url)`. |
| `university_id`, `university_name`, `country` | | Denormalized from the registry for convenience. |
| `title` | string | Extracted or registry-provided title. |
| `source_url`, `canonical_url` | string | Where the document came from. |
| `publication_date`, `last_updated_date` | date, nullable | From the source page/PDF metadata where available. |
| `retrieval_timestamp` | datetime | When this collection run fetched the document. |
| `original_language` | string, nullable | Unknown unless confirmed. |
| `analyzed_language` | string | Language actually analyzed (`en` for the pilot). |
| `is_official_translation` | bool, nullable | `null` = unknown. |
| `translation_status` | enum | `original`, `official_translation`, or `unknown`. |
| `local_language_url` | string, nullable | A parallel local-language version's URL, if known. |
| `english_version_url` | string, nullable | Set when the collected page IS the English version and a separate canonical URL exists. |
| `other_language_documents_may_exist` | bool, nullable | Researcher-entered flag, never inferred automatically. |
| `language_scope_note` | string, nullable | Free-text caveat about language scope for this document. |
| `document_type`, `intended_audience`, `policy_level` | | As in the registry. |
| `file_format` | string | `html` or `pdf`. |
| `http_status` | int, nullable | HTTP status code from collection. |
| `robots_allowed` | bool, nullable | `null` = could not be determined. |
| `extraction_method` | enum | `html_http`, `pdf_http`, `selenium`, `not_applicable`. |
| `raw_text` | string | Extracted text before cleaning (empty for PDFs -- see `cleaned_text`). |
| `cleaned_text` | string | Normalized, boilerplate-stripped text used for all downstream analysis. |
| `text_hash` | string, nullable | SHA-256 of normalized `cleaned_text`; used for de-dup and change detection. |
| `word_count` | int | Word count of `cleaned_text`. |
| `duplicate_of` | string, nullable | Set if this document is an exact-hash duplicate of another. |
| `collection_status` | enum | `pending`, `collected`, `unchanged`, `failed`, `skipped_not_verified`, `skipped_robots_disallowed`. |
| `error_message` | string, nullable | Set on failure/skip. |
| `manual_verification_status` | string, nullable | Free-text note on manual review status. |
| `redistribution_allowed` | bool, nullable | Whether the source's terms are confirmed to allow redistributing its text. |
| `license_note` | string, nullable | Free-text license/redistribution note. |
| `terms_checked` | bool | Whether a human has checked this document's terms of use. Defaults `false`. |
| `terms_url` | string, nullable | The terms-of-use page checked, if any. |
| `copyright_notice` | string, nullable | Verbatim copyright line found on the source, if any. |
| `tdm_reservation_detected` | bool, nullable | Whether a text-and-data-mining reservation was detected. `null` = not checked (automated detection is not implemented -- see `docs/legal_and_compliance.md`). |
| `legal_review_status` | enum | `pending` (default) / `reviewed_redistribution_allowed` / `reviewed_redistribution_restricted` / `restricted`. |

## `dimension_scores` table (long format: one row per document x dimension x coding round)

| Field | Type | Description |
|---|---|---|
| `document_id`, `dimension_id`, `axis` | | Foreign keys / classification. |
| `score` | int (0-2) | The ordinal coding decision. |
| `evidence_passage` | string, nullable | Required (enforced at the schema level) when `score > 0`. |
| `evidence_start_offset`, `evidence_end_offset` | int, nullable | Character offsets into `cleaned_text`. |
| `uncertainty_flag` | bool | Whether the coder was genuinely torn. |
| `uncertainty_note` | string, nullable | What the coder was torn between. |
| `coder_id` | string | e.g. `patricia`, or `rule_based_v1`. |
| `coder_type` | enum | `human` or `rule_based` -- these are never merged into one score. |
| `coding_timestamp` | datetime | When this score was recorded. |
| `coding_round` | int | 1 = initial coding, 2 = a recoding pass (e.g. the intra-coder check). |

## `index_results` table

Holds all three index KINDS -- automated exploratory hints, human-coded
indices, and validated indices -- in one table, distinguished by two
columns rather than by table (see `database.py`'s module-level note for
why): `index_name` is always one of the six `IndexKind` values
(`automated_rei_hint`, `automated_pisi_hint`, `human_rei`, `human_pisi`,
`validated_rei`, `validated_pisi` -- never a bare `"REI"`/`"PISI"`), and
`index_kind` is the coarser category (`automated_hint` | `human` |
`validated`) derived from it. `dashboard/components/data_access.py`
provides `load_automated_hints_df()` / `load_human_index_results_df()` /
`load_validated_index_results_df()` so callers read exactly one kind
without risking an accidental blend.

| Field | Type | Description |
|---|---|---|
| `document_id` | | |
| `index_name` | enum (`IndexKind`) | One of `automated_rei_hint`, `automated_pisi_hint`, `human_rei`, `human_pisi`, `validated_rei`, `validated_pisi`. |
| `index_kind` | enum | `automated_hint` / `human` / `validated` -- derived from `index_name`, never set independently. |
| `raw_score` | float | Sum of (weighted) component scores. |
| `normalized_score` | float (0-100) | Normalized against the coded dimensions' max possible score. |
| `n_dimensions_total`, `n_dimensions_coded`, `n_dimensions_missing` | int | Coverage bookkeeping. |
| `component_scores_json` | JSON string | `{dimension_id: score}` for every coded dimension -- never backfilled with 0s for missing ones. |
| `weighting_scheme` | string | `equal` (baseline) or a named custom scheme. |
| `confidence` | float (0-1) | `n_dimensions_coded / n_dimensions_total`. |
| `coder_type` | enum | `human` or `rule_based`. |
| `coding_round` | int | Which coding round produced this (relevant for `human`/`validated` rows). |
| `computed_at` | datetime | |

A `human_rei`/`human_pisi` row exists **only** when every dimension in
that axis has a complete human annotation for that document/round --
otherwise no row is written at all, and the dashboard must show "Not yet
human-coded" rather than treat the absence as zero. A
`validated_rei`/`validated_pisi` row exists only once a complete,
independent round-2+ recoding exists for that document/axis. See
`modeling/indices.py`.

## `collection_audit` table

One row per collection *attempt* (not per document) -- university, URL,
timestamp, outcome, HTTP status if any, error message if any, and
retrieval method. This is the append-only log behind
`outputs/reports/collection_audit.md`.

## `data/processed/chunks.parquet`

One row per document chunk: `chunk_id`, `document_id`, `university_id`,
`chunk_index`, `chunk_text`, `word_count`. Produced by
`scripts/process_documents.py`.

## `data/processed/topic_assignments.parquet`

One row per chunk with its BERTopic assignment: `chunk_id`, `document_id`,
`university_id`, `chunk_index`, `topic_id` (`-1` = outlier),
`topic_probability`, `is_outlier`. Produced by `scripts/train_topics.py`.
