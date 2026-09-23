# Annotation data release

This document explains what annotation data from the pilot is public, what
is kept private, and why -- following the recommendation in the project's
public-release audit (`outputs/reports/public_release_audit.md`, a local
working document, and Option 4 of its recommendations).

## What was coded

The pilot's human coding used **one human coder** (round 1 only, no second
round or intercoder check). That coder completed **90 dimension
decisions**: 5 documents x 18 coding dimensions each (7 Restriction and
Enforcement Index dimensions, 11 Pedagogical Integration and Support Index
dimensions -- see `docs/coding_guide.md`). Every score of 1 or 2 required a
stored evidence passage from the source document; a score of 0 required
none.

## What is public

`data/annotations/pilot_scores_public.csv` contains exactly the 90
dimension scores needed to reproduce the pilot's human REI and PISI index
values -- `document_id`, `university_id`, `dimension_id`, `axis`, `score`,
`uncertainty_flag`, `coder_type`, `coding_round` -- and nothing else. It
contains no evidence text, no evidence offsets, no timestamps, no coder
name, and no personal information of any kind. Recomputing REI and PISI
from this file alone reproduces the pilot's published index values exactly
(see `docs/pilot_analysis.md`).

`data/annotations/annotation_template.example.csv` is an empty template:
the same column headers used for full annotation work, with no completed
rows and no evidence passages. Anyone starting a new coding project (for
example, a second coder joining the pilot, or a contributor beginning
Phase 2 coding) should copy this file locally as their own working
annotation file rather than editing it in place or reusing pilot data.

## What is private, and why

The complete annotation file -- including every evidence passage, the
coder's uncertainty notes, and timestamps -- is preserved at
`data/annotations/private/pilot_annotations_complete.csv` (git-ignored) and
remains available locally at `data/annotations/annotation_template.csv`
(also git-ignored) for the existing pilot scripts and dashboard, which
still read from that path.

Full evidence is not published for two related reasons:

1. **Reconstruction risk.** Evidence passages are direct excerpts of the
   source policy documents. Summed per document across all 18 coding
   dimensions, they reconstruct a substantial portion of several source
   documents' text -- in two of the five pilot documents, at or above the
   document's total word count, because passages cited for different
   dimensions can overlap (see the audit for the full per-document
   breakdown). Publishing the evidence column would, in effect, publish
   most or all of several source policies' full text.
2. **Unconfirmed redistribution rights.** Every one of the five pilot
   sources currently has `legal_review_status=pending` and
   `terms_checked=false` in `config/universities.csv` -- no source's
   redistribution rights have been confirmed. This is the same reasoning
   the project already applies to raw collected document text (see
   `docs/legal_and_compliance.md`), extended here because the evidence
   passages present a comparable exposure risk for the same
   not-yet-confirmed sources.

Withholding full evidence text is a copyright and responsible-data-
management precaution, not a methodological limitation: the human-coded
scores themselves, which are this pilot's substantive research result, are
fully public and fully reproducible from `pilot_scores_public.csv`.

The private, complete evidence file remains available for internal
validation -- for example, a second coder checking the first coder's
reasoning, or the researcher revisiting a specific score -- and for
potential controlled review (for example, sharing the private file
directly with a supervisor or journal reviewer under its own agreement),
without being published broadly.

## What this release does not claim

- **No intercoder reliability is claimed.** The pilot used one coder and
  one coding round; `coding_round` in the public file is always `1`, and
  no weighted-kappa or agreement statistic exists yet for this pilot (see
  `docs/limitations.md`).
- **The public scores file is not a substitute for the original policy
  documents.** It reports how the coder scored each dimension, not the
  documents' text. Anyone wanting to read a source document itself should
  follow the link to the original in `config/universities.csv` (the
  source registry) or `docs/pilot_analysis.md` (the pilot report), which
  lists each institution's document title and, where available, its
  public URL.

## Data dictionary: `pilot_scores_public.csv`

| Column | Type | Description |
|---|---|---|
| `document_id` | string | Stable identifier for the specific collected document (one per institution in this pilot). |
| `university_id` | string | Short identifier for the institution (e.g. `lund_se`), matching `config/universities.csv`. |
| `dimension_id` | string | One of the project's 18 coding dimensions (e.g. `prohibition_restriction`, `ai_literacy`), defined in `config/coding_dimensions.yaml` and `docs/coding_guide.md`. |
| `axis` | string | Which index this dimension belongs to: `restriction_enforcement` (REI, 7 dimensions) or `pedagogical_support` (PISI, 11 dimensions). |
| `score` | integer (0, 1, or 2) | The coder's ordinal score for this dimension: 0 = absent, 1 = mentioned, 2 = emphasized. See `docs/coding_guide.md` for the full scoring rubric. |
| `uncertainty_flag` | boolean (`True`/`False`) | Whether the coder flagged this score as uncertain. The accompanying free-text `uncertainty_note` (which may reference or paraphrase source wording) is withheld along with the evidence passages, for the same reasons above. |
| `coder_type` | string | Always `human` in this pilot (as opposed to `automated`, the pipeline's separate rule-based hint layer, which is not human coding and is reported only in the exploratory automated-hints comparison in `docs/pilot_analysis.md`). |
| `coding_round` | integer | Always `1` in this pilot (no second coding round or intercoder check has been performed yet). |

Row count: 90 (5 documents x 18 dimensions). Sorted deterministically by
`university_id`, then `axis`, then `dimension_id`.
