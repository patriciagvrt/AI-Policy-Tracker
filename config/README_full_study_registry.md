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

## Current state

Both files contain headers only. No institutions, sources, URLs, or
selection decisions have been populated. Populating them is a later
Phase 2 step, not part of this foundation scaffolding.
