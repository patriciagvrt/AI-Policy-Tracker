# Nordic University AI Policy Tracker

A reproducible pipeline that collects, processes, codes, and visualizes
official Nordic university guidance on generative AI in higher education.
**This is a five-university pilot** (Sweden, Norway, Denmark, Finland,
Iceland -- one institution per country), built to test the full pipeline
end to end before scaling to 30+ universities.

## Project motivation

European and Nordic universities have rapidly published guidance on
generative AI, ranging from strict prohibition-and-penalty language to
teaching-integration and AI-literacy resources -- often within the same
document. Existing commentary tends to flatten this into a single
"strict vs. permissive" narrative. This project instead treats restriction
and pedagogical support as **two independent dimensions** that a policy can
score on simultaneously, and builds a transparent, auditable, human-
validated system for measuring both.

## Pilot research question

How do selected Nordic universities frame the use of generative AI in
higher education, particularly regarding restriction, academic integrity,
pedagogy, AI literacy, and student support?

## Conceptual framework

Two independent axes, never combined into one score:

- **Restriction and Enforcement Index (REI)** -- prohibition, punishment,
  academic misconduct framing, AI detection/surveillance, mandatory
  disclosure, assessment control, privacy/security restrictions.
- **Pedagogical Integration and Support Index (PISI)** -- permitted/
  encouraged use, AI literacy, critical evaluation, responsible use,
  teaching integration, student support, staff support, transparency/
  citation guidance, equity/accessibility/inclusion, privacy awareness,
  human oversight.

A document can score high on both, low on both, or high on one and low on
the other. See `docs/methodology.md` and `docs/coding_guide.md` for full
detail, and `docs/limitations.md` before interpreting any result.

## Pilot universities

| Country | University | Document | Type |
|---|---|---|---|
| Sweden | Lund University | Policy on Principles for the Use of Generative AI at Lund University | Institution-wide policy (PDF) |
| Norway | University of Oslo | How to use AI as a student | Student guidance |
| Denmark | Aarhus University | Generative artificial intelligence (GAI) | Student/exam guidance |
| Finland | Aalto University | Guidance for the use of AI in teaching and learning | Teaching & learning guidance |
| Iceland | Reykjavik University | Guiding Principles for the Use of AI in Teaching and Learning at RU | Teaching & learning guidance / exam regulation |

All five sources are recorded in `config/universities.csv` as
`verification_status=verified`, `active=true`, `selection_status=pilot_selected`.

## Pilot status

| Item | Final pilot status |
|---|---|
| Universities | 5 |
| Successfully collected documents | 5 |
| Human-coded decisions | 90 |
| REI dimensions per document | 7 |
| PISI dimensions per document | 11 |
| Text chunks | 29 |
| Experimental BERTopic topics | 3 |
| Outlier chunks | 3 |
| Human coders | 1 |
| Representativeness | Pilot only |

**How to read these results.** The human-coded REI/PISI indices are this
pilot's substantive research results -- one coder's complete reading of
every dimension for every document, evidence-backed for every score of 1
or 2. The automated index hints are exploratory only: a rule-based,
negation-aware keyword matcher used to surface candidate evidence for a
human coder, never a validated replacement for human interpretation, and
they diverge substantially from the human-coded scores (see
`docs/pilot_analysis.md`). BERTopic's topic-model output is likewise
experimental: it was fit on only 5 documents and 29 chunks, far too few
for the resulting topics to be considered stable or generalizable, and two
of the three topics are institution-specific rather than cross-institution
themes. With one human coder and five documents, this pilot is not
representative of Nordic or European higher education, supports no
university or country ranking, and cannot test whether REI and PISI are
statistically associated with one another.

The public, tracked copy of the full pilot analysis is
`docs/pilot_analysis.md` (identical in content to the generated
`outputs/reports/pilot_analysis.md`, which stays local and git-ignored).
Phase 2 development -- expanding to 30+ universities -- happens on the
`phase-2-30-universities` branch; the `v0.1-pilot` tag preserves this
five-university pilot as a fixed historical milestone. The pilot's SQLite
database and Parquet outputs are git-ignored (derived, regenerable data)
and are additionally preserved through a checksum-verified local archive
snapshot under `data/archive/`.

## Architecture

```
config/       -- source registry, coding dimensions, settings
src/nordic_ai_policy_tracker/
  collection/   -- robots.txt check, HTML/PDF extraction, crawler
  processing/   -- cleaning, language detection, segmentation, dedup
  modeling/     -- rule-based indicators, REI/PISI indices, validation, BERTopic
  database.py   -- SQLite access layer
  schemas.py    -- pydantic data models (the single source of truth for every table)
scripts/      -- one script per pipeline stage (see below)
dashboard/    -- Streamlit app (app.py + pages/)
tests/        -- pytest suite, local fixtures only, no live network
docs/         -- methodology, coding guide, data dictionary, limitations, ethics, legal & compliance
```

## Installation (Windows / PowerShell)

Requires Python 3.11+. These are the commands to run in PowerShell (e.g.
the integrated terminal in VS Code):

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

If PowerShell refuses to run the activation script (an execution-policy
error), this is a per-session, process-scoped workaround -- it only
affects the current PowerShell window and reverts when that window is
closed:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

**Do not** set a permanent, system-wide execution-policy change (e.g. `-Scope
CurrentUser` or `-Scope LocalMachine`) just to run this project -- the
command above is deliberately scoped to the current process only.

<details>
<summary>macOS / Linux (bash/zsh)</summary>

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

</details>

## Environment setup

No secrets are required for the pilot (all sources are public). Copy
`.env.example` to `.env` if you want to override the default user agent,
request delay, or database path.

## Data collection

```powershell
python scripts/collect_documents.py --live
```

The collector checks `robots.txt` before fetching, never bypasses
authentication/CAPTCHAs/rate limits, and stops immediately (no retries) on
a 403 or 429 response -- see `docs/legal_and_compliance.md`.

This reads `config/universities.csv`, collects every `active=true` +
`verification_status=verified` source, and writes to
`data/processed/policy_tracker.db` plus
`outputs/reports/collection_audit.md`.

**Final pilot collection result:** all five documents, including Lund
University's PDF, were collected successfully through the project's live
HTTP collection pipeline -- 5 attempted, 5 collected, 0 failures, 0
duplicates (see `outputs/reports/collection_audit.md`). No browser-
automation fallback, sandbox substitute, or fabricated/summarized stand-in
text was used for any of the five final pilot documents. An earlier
development environment could not reach university websites directly and
used a documented substitute-retrieval step for some sources during
pipeline testing; that step is not part of the final pilot corpus and is
retained only as historical development context under
`data/raw/pilot_sandbox_retrieved/`.

## Processing

```bash
python scripts/process_documents.py
```

Deduplicates, segments documents into chunks (`data/processed/chunks.parquet`),
and writes `outputs/reports/data_quality_report.md`.

## Human annotation

1. Read `docs/coding_guide.md`.
2. Launch the dashboard (see below) and use the **Annotation** page, or
   edit `data/annotations/annotation_template.csv` directly (this complete
   file, with full evidence text, stays local and is git-ignored -- see
   below).
3. Every score of 1 or 2 requires an evidence passage -- this is enforced
   by the schema, not just a guideline.

**Three forms of this pilot's annotation data, not to be confused:**

- `data/annotations/annotation_template.csv` (local only, git-ignored) --
  the complete working file the pipeline and dashboard read and write,
  including full evidence passages. This is what pilot scripts use.
- `data/annotations/private/pilot_annotations_complete.csv` (local only,
  git-ignored) -- a preserved, verified copy of the complete file above,
  kept for internal validation.
- `data/annotations/pilot_scores_public.csv` (tracked in git) -- the
  public, scores-only dataset: no evidence text, no timestamps, no coder
  name. Reproduces the published human REI/PISI values exactly. See
  `docs/annotation_data_release.md` for the full explanation and why full
  evidence is not published.
- `data/annotations/annotation_template.example.csv` (tracked in git) --
  an empty template (headers only, no pilot data) to copy locally when
  starting a new coding project.

## Index calculation

```powershell
python scripts/calculate_indices.py                 # automated exploratory hints only
python scripts/calculate_indices.py --include-human  # + human/validated indices, once annotation.csv has real data
```

This project computes and stores three distinct index KINDS -- never
labeled with a bare "REI"/"PISI" and never blended together:
`automated_rei_hint`/`automated_pisi_hint` (always computed, an
exploratory rule-based hint, never the researcher's interpretation),
`human_rei`/`human_pisi` (only once every dimension in that axis has a
complete human annotation -- otherwise the dashboard shows "Not yet
human-coded"), and `validated_rei`/`validated_pisi` (only once a complete
round-2+ intra-coder recoding exists). See `docs/methodology.md`.

**The Policy Matrix dashboard page defaults to the human-coded view.** If
no human coding has been completed yet, it shows an empty plot with an
explanation rather than silently substituting the automated hints -- switch
to "Automated exploratory hints" in the page's toggle to see those instead.

## BERTopic (exploratory topic modeling)

```powershell
python scripts/train_topics.py
```

Requires `data/processed/chunks.parquet` to exist. Refuses to fit a model
(and says so, in `outputs/reports/topic_model_report.md`) if the corpus is
too small.

**Final pilot result:** the configured `all-MiniLM-L6-v2` sentence-
transformer model was successfully used (not the local TF-IDF fallback the
pipeline falls back to when that model can't be downloaded), producing 3
topics and 3 outlier chunks across the corpus's 29 chunks --
`topic_method=bertopic_sentence_transformer`,
`semantic_embeddings_used=true`, `topic_status=experimental`. It remains
labeled experimental regardless of which embedding path is used: this
pilot's five-document, 29-chunk corpus is too small for the resulting
topics to be considered stable or generalizable, and two of the three
topics are already institution-specific rather than cross-institution
themes (see `outputs/reports/topic_model_report.md` and
`docs/pilot_analysis.md`). See `docs/methodology.md` and
`docs/limitations.md`.

## Dashboard

```powershell
streamlit run dashboard/app.py
```

Pages: Overview, Nordic Map, Policy Matrix (the REI x PISI scatter plot --
defaults to human-coded indices), Topic Explorer, Document Comparison,
Methodology & Limitations, and Annotation.

## Testing

```powershell
pytest
ruff check .
black --check .
```

All tests use local fixtures under `tests/fixtures/` -- no test depends on
live network access. Coverage includes configuration validation,
active-source filtering, HTML/PDF extraction, text cleaning (including
personal-contact-info stripping), segmentation, deduplication,
negation-sensitive rule-based indicator suggestions (including the exact
"AI detectors are unreliable..." example from the project brief), the
three index kinds' completeness gating (automated hints always computed;
human/validated indices only when their respective axis is completely
coded), index score boundaries and missing-value handling,
unequal-dimension-count normalization, failed-source handling
(including no-retry-on-403/429), hashing/stable-ID creation, and language
detection.

## Ethical considerations

Public documents only, respectful crawling (robots.txt, delays, a
descriptive user agent), full source attribution, no institutional
ranking. See `docs/ethics.md`.

## Limitations

Read `docs/limitations.md` before drawing any conclusion from this pilot's
output. In short: five documents, one per country, is a pipeline test, not
a representative study of anything.

## Reproducibility

Every document, score, and index carries its provenance: source URL,
retrieval timestamp, extraction method, coder ID/type, and (for indices)
the exact dimensions coded vs. missing. Random seeds are fixed where
applicable (BERTopic/UMAP: `config/settings.yaml::bertopic.random_seed`).

## Future multilingual extension

The schema already carries `original_language`, `analyzed_language`,
`is_official_translation`, `translation_status`, and
`other_language_documents_may_exist` on every document, and
`processing/language.py` already does language detection/confirmation.
Extending to native-language documents means: (1) adding a multilingual
sentence-embedding model option to `config/settings.yaml::bertopic`,
(2) building or sourcing dimension-keyword dictionaries per language
(`config/coding_dimensions.yaml` would need a `keyword_hints_by_language`
structure), and (3) deciding, explicitly, whether cross-language REI/PISI
comparisons are valid given each language's dictionary quality --
see `docs/limitations.md`.

## Future 30+ university expansion

`config/universities.csv` already carries the stratification fields
(`institution_type`, `size_category`, `technical_or_comprehensive`,
`selection_status`, `selection_rationale`, `exclusion_rationale`) needed
to document a deliberate Nordic-stratified sample (~6 per country) rather
than convenience sampling. Every new source must be verified (working
URL, official domain, substantive generative-AI content, identifiable
audience, recorded language) before being marked `active=true`.

## Citation

If you use this pipeline or its pilot data, cite it as:

> Cruz, P. (2026). *Nordic University AI Policy Tracker* (pilot version).
> Unpublished research project pipeline, Linköping University.

## Roadmap

- [x] Collect all five sources with `--live` from a normally-networked machine.
- [x] Complete human coding of the pilot (see `dashboard/pages/7_Annotation.py`).
- [ ] Intra-coder recoding pass, to populate the `validated_rei`/`validated_pisi` indices.
- [ ] Expand to 30+ universities on the `phase-2-30-universities` branch (see the Phase 2 Expansion Plan; foundation scaffolding -- separate registry and settings files, archival snapshot -- is in place, institutions not yet populated).
- [ ] Add a second coder; compute weighted Cohen's kappa.
- [ ] Extend to native-language documents per country.

## Screenshots

_(Add dashboard screenshots here once you've run it against live-collected data.)_
