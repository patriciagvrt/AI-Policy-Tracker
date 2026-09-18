# Methodology

## Unit of analysis

The primary unit is the individual policy or guidance **document**. This
pilot has exactly one document per university (five documents total), but
the schema and code support multiple documents per university (an
institution-wide policy, an exam regulation, student guidance, staff
guidance, and so on) — see `docs/data_dictionary.md`. Document-level scores
aggregate to **university-level** and then to **country-level** measures,
with document-level detail always preserved and always reachable from any
aggregate figure shown in the dashboard.

## Pilot sampling

Five Nordic universities were selected, one per country (Sweden, Norway,
Denmark, Finland, Iceland), based on having a publicly accessible,
substantively generative-AI-specific policy or guidance document in
English at the time of collection. This is **not** a random or
representative sample. It exists to test the pipeline end to end: source
configuration, collection, extraction, cleaning, language handling,
segmentation, rule-based indicator assistance, human coding structure,
index construction, exploratory topic modeling, and the dashboard. See
`docs/limitations.md` for what this pilot cannot support.

## Language protocol

Version 1 analyzes English-language documents only — either the
university's original English drafting or an official English translation,
where that distinction could be confirmed. It does **not** machine-translate
non-English policies for the primary analysis, and it does **not** assume an
English page represents a university's entire policy environment, or that
the absence of a found English page means the university has no AI policy
at all. Every document records `original_language`, `analyzed_language`,
`is_official_translation`, `translation_status`, and
`other_language_documents_may_exist` — left blank/unknown rather than
guessed wherever the source page didn't make the answer clear. The dataset
is described precisely as: *"Publicly available English-language AI
guidance from selected Nordic universities."*

## Collection process

`src/nordic_ai_policy_tracker/collection/crawler.py` reads
`config/universities.csv`, filters to rows marked both `active=true` and
`verification_status=verified`, checks `robots.txt`, applies a delay and
limited retries, downloads HTML or PDF content, and extracts the main text
(`html_extractor.py` / `pdf_extractor.py`), stripping navigation, cookie
banners, and other boilerplate. Raw and cleaned text are stored separately.
A content hash (`utils/text_hashing.py`) supports duplicate detection and
unchanged-content skipping on re-collection. Every attempt — success or
failure — is logged to a `collection_audit` table and summarized in
`outputs/reports/collection_audit.md`. One source failing does not stop
collection of the others.

**This pilot's specific build ran inside a network-sandboxed environment**
that could not reach arbitrary external domains. Four of five documents'
text was retrieved through a one-time, clearly-documented substitute
retrieval step (see `data/raw/pilot_sandbox_retrieved/README.md`); the
fifth (Lund University's PDF) could not be retrieved verbatim at all in
that environment and is recorded as a genuine collection failure, not
approximated. Every processing step *after* retrieval (cleaning, hashing,
language detection, segmentation, indicator scoring) ran identically to how
it would run in a normal environment. Re-running
`python scripts/collect_documents.py --live` from a machine with regular
internet access is the way to collect all five documents for real.

## Coding dimensions

Eighteen dimensions, seven under the Restriction and Enforcement Index
(REI) and eleven under the Pedagogical Integration and Support Index
(PISI) — see `config/coding_dimensions.yaml` for the authoritative list and
`docs/coding_guide.md` for full definitions, inclusion/exclusion criteria,
and worked examples per dimension.

## REI and PISI

Both indices are built the same way from a document's coded dimensions:
raw score = sum of component scores (each 0-2); normalized score (0-100)
= raw score divided by the maximum possible score **for the dimensions
actually coded** (never divided by the full dimension count with missing
values silently treated as 0); confidence = (dimensions coded) / (total
dimensions in that axis). Equal weighting is the documented baseline;
`modeling/indices.py::sensitivity_analysis` supports recomputing under
alternative, explicitly-named weighting schemes. **REI and PISI are never
combined into one score** — see `modeling/indices.py`'s module docstring
for the reasoning, which follows directly from this project's core
interpretive stance: restriction and pedagogical support are independent
axes, not opposite ends of one scale.

## BERTopic's role

BERTopic (`modeling/bertopic_pipeline.py`) is used only for **exploratory**
thematic discovery over document chunks. It never produces or informs a
REI/PISI score (of any kind — automated, human, or validated). With fewer
documents or chunks than configured minimums, the pipeline refuses to fit
a model rather than fabricate one. This pilot's five documents are far too
few for stable, generalizable topics — every topic-model output in the
dashboard and reports is labeled experimental.

Every topic-model run records three explicit fields alongside its output:
`topic_method` (`"bertopic_sentence_transformer"` or `"tfidf_fallback"`),
`topic_status` (always `"experimental"` for this pilot), and
`semantic_embeddings_used` (`true`/`false`). This pilot's own build ran in
a sandbox with no network path to huggingface.co, so it could not download
the configured sentence-transformer model and used the TF-IDF fallback —
`topic_method=tfidf_fallback`, `semantic_embeddings_used=false`. **This is
not the final BERTopic analysis.** The topic model should be re-run on a
machine with normal internet access (`python scripts/train_topics.py`) so
the configured sentence-transformer model can actually be used, before its
output is treated as anything beyond a pipeline smoke test — see
`dashboard/components/labels.py::BERTOPIC_DISCLAIMER` and
`docs/limitations.md`.

## Three index kinds: automated hint, human, validated

This project computes and stores three distinct KINDS of index value,
never blended and never presented as interchangeable — see
`schemas.py::IndexKind` and `modeling/indices.py` for the authoritative
definitions:

- **`automated_*_hint`** (`automated_rei_hint`, `automated_pisi_hint`).
  `modeling/indicators.py` provides negation-aware keyword matching as a
  research aid: it finds candidate sentences for a dimension and flags
  whether each looks negated/hedged, but it does not itself decide a score
  with confidence — `suggest_rule_based_score()` is a conservative
  starting hypothesis. These hints are always computed for every
  successfully collected document, even from partial rule-based coverage,
  and are **never presented as the researcher's own interpretation** of
  the document — every place they appear in the dashboard carries an
  explicit disclaimer (`dashboard/components/labels.py`).
- **`human_rei`/`human_pisi`**. Computed **only** from the pilot's sole
  human coder's (Patricia's) COMPLETE annotation of every dimension in
  that axis, for one document, for one coding round
  (`modeling/indices.py::compute_human_index_for_axis`). If any dimension
  in the axis is uncoded, no `human_*` row is produced at all — the
  dashboard shows "Not yet human-coded," never a partial or imputed
  number. **This is the dashboard's default view.**
- **`validated_rei`/`validated_pisi`**. A `human_*` result that has
  additionally passed this pilot's intra-coder recoding check (a
  complete, independent round-2+ coding of the same document/axis — see
  "Human validation" below). For this pilot, no document has a
  `validated_*` result yet, since no recoding round has been run.

All three kinds are stored in the same `index_results` table, distinguished
by an `index_kind` column (`'automated_hint' | 'human' | 'validated'`) —
see `database.py`'s module-level note for why a single table with a
strictly-typed `index_name`/`index_kind` pair was chosen over three
separate tables.

## Human validation

A single coder (Patricia) for the pilot. No inter-coder reliability is
reported for the pilot; weighted Cohen's kappa is documented as the planned
statistic once a second coder joins (`modeling/validation.py`). An
intra-coder check is planned instead: recoding all five documents after a
~2-3 week interval and comparing round 1 vs. round 2
(`modeling/validation.py::compare_coding_rounds`,
`intra_coder_agreement_rate`) — reported as a plain agreement percentage,
explicitly not claimed to rule out individual coder bias. Once a document's
round-2 recoding is complete for an axis,
`modeling/indices.py::compute_validated_index_for_axis` will start
producing a `validated_*` result for it automatically; nothing else needs
to change.

## Evidence storage

Every non-zero score (human or rule-based) is stored with a verbatim
evidence passage. Human-coded evidence additionally supports character
offsets into the document's cleaned text. This is enforced at the schema
level (`schemas.py::DimensionScore`): constructing a `DimensionScore` with
`score > 0` and no `evidence_passage` raises a validation error.
