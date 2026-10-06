# Phase 2 registry design: `institutions_full.csv` and `sources_full.csv`

This note documents the two files that replace the pilot's single-file
`universities.csv` registry for the 30+ university expansion (Phase 2 /
"full study"). Both files are currently **header-only scaffolding**: no
institutions or source URLs have been added yet, and none should be added
until they are verified. See the Phase 2 Expansion Plan for the full
rationale (Sections 3 and 4).

## Why two files instead of one

The pilot collected exactly one document per institution, so one row per
university was enough. Phase 2 allows an institution to contribute more
than one document source (a central policy, plus teaching guidance, plus
exam rules, for example), so institution-level facts and source-level
facts are split into two linked tables.

## `institutions_full.csv`

One row per institution. Columns describe the institution itself:
country, city, coordinates, institution type, size category, whether it
is technical or comprehensive, public or private, and whether it overlaps
with a pilot institution (`pilot_overlap`). `selection_status`,
`selection_rationale`, and `exclusion_rationale` track why an institution
is or isn't part of the study frame.

## `sources_full.csv`

One row per document *source*. `institution_id` may repeat any number of
times here: an institution with three collected document sources has
three rows in this file, all sharing its `institution_id`. Every non-empty
row in this file must reference an `institution_id` that exists in
`institutions_full.csv`.

Key columns:

- `source_role` starts as either `primary_candidate` or `supplementary`
  at registry time. It is not yet the institution's final primary
  document -- that is decided during collection by applying the documented
  source hierarchy (institution-wide policy > teaching/learning guidance >
  student guidance > examination guidance; see Phase 2 Expansion Plan,
  Section 4). Exactly one source per institution becomes `primary`; every
  other collected source for that institution stays `supplementary` and
  never enters the main REI/PISI comparison.
- `original_language`, `original_language_status` (`verified` /
  `inferred` / `unknown`), and `expected_language` support the
  multilingual data model described in the Phase 2 Expansion Plan,
  Section 6.
- `verification_status`, `terms_checked`, `terms_url`, and
  `legal_review_status` mirror the pilot's compliance fields. No
  institution should be treated as selected for collection until its
  source and legal metadata here have actually been verified -- an empty
  or `pending` value in these columns means the source is not yet cleared
  to collect.

## `institutions_full.csv` -- added institution-level columns

The institution-registry population step (following this foundation
scaffolding) added seven columns not present in the pilot-era schema, to
support cross-national comparison and the Icelandic federation structure:

- `official_website` -- the institution's homepage URL. Never a policy
  document URL; that belongs only in `sources_full.csv`.
- `institutional_profile` -- a short human-readable description of the
  institution's type (e.g. "Technical university", "Business school").
- `primary_comparison_family` -- a controlled-vocabulary category used to
  group institutions for cross-national comparison (e.g.
  `comprehensive_research_university`, `technical_university`,
  `business_school`, `applied_sciences_university`,
  `arts_specialized_institution`, `specialized_institution`).
- `comparison_tags` -- semicolon-separated descriptive tags supplementing
  the primary family (e.g. `research_intensive;comprehensive`).
- `inclusion_method` -- how the institution entered the full-study sample:
  `national_census` for Iceland (all seven Icelandic institutions are
  included, since Iceland's full higher-education population is small
  enough to include exhaustively) or `stratified_sample` for the other
  four countries (seven institutions each, sampled to represent the
  national landscape of institution types).
- `governance_status` -- `independent` for nearly every institution;
  `federation_lead` for the University of Iceland and `federated_member`
  for University of Iceland at Hólar, reflecting Hólar's status as a
  federated member of the University of Iceland.
- `parent_institution_id` -- blank except for `holar_is`, which points to
  `hi_is`.

The pilot-era columns (`city`, `latitude`, `longitude`, `institution_type`,
`size_category`, `technical_or_comprehensive`, `public_or_private`,
`exclusion_rationale`) are preserved in the schema but intentionally left
blank for the 35 full-study rows at this stage -- populating them
precisely (especially geocoordinates) is a separate, later task, not
inferred here.

## Current state

`institutions_full.csv` now holds all 35 full-study institutions (7 per
Nordic country: Sweden, Norway, Denmark, Finland, Iceland), each with
`selection_status=full_study_selected`. `sources_full.csv` remains
header-only: no document sources, URLs, or source-level selection
decisions have been populated yet. Populating `sources_full.csv` -- and
any document collection -- is a later Phase 2 step, not part of this
institution-registry stage.
