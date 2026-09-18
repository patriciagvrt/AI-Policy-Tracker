# Ethics

## Public data use

This project collects only content that is already publicly accessible on
official university web domains, without logging in, bypassing a
paywall, or circumventing any access control. `config/universities.csv`
only lists sources a human has verified as public, official, and
substantive before the collector is allowed to fetch them
(`verification_status=verified` and `active=true` are both required —
see `collection/crawler.py::read_active_verified_sources`).

## Respectful crawling

The collector (`collection/crawler.py`) checks `robots.txt`
(`collection/robots.py`) before fetching, uses a descriptive, identifying
user agent naming the project and a contact email
(`config/settings.yaml::collection.user_agent`), applies a delay between
requests, and limits retries. A source disallowed by `robots.txt` is
skipped, not overridden. Content-hashing avoids repeated unnecessary
downloads of unchanged pages.

## Source attribution

Every collected document retains its original source URL, and the
dashboard's Document Comparison, Nordic Map, and Policy Matrix pages all
link back to the original page for every document shown. No document's
content is presented without a visible link to where it came from.

## Copyright and redistribution

University policy text is presumably © the issuing institution. This
project's own code (this repository) is MIT-licensed; the collected
policy *text* is not, and is not implied to be. The schema includes
`redistribution_allowed`, `license_note`, `terms_checked`, `terms_url`,
`copyright_notice`, `tdm_reservation_detected`, and `legal_review_status`
fields (all currently unset/pending, since no case-by-case legal read has
been performed yet for any of the five pilot sources) precisely so that,
if a university's terms restrict redistribution, this project can store
metadata, derived indicators, and short lawful evidence excerpts instead
of full text, with instructions for reproducing collection from the
original public source rather than redistributing a copy. `.gitignore`
excludes `data/raw/` (all of it, including any format-specific PDFs,
HTML, or extracted text) from version control by default for this
reason — collected raw text is treated as something to regenerate via the
pipeline, not something to publish as a dataset, unless a specific
source's terms are confirmed to allow it. See `docs/legal_and_compliance.md`
for the full collection-time legal procedure (terms-of-use checking, no
bypassing access controls, retry-stopping on 403/429, and the excerpt
citation requirements).

## Non-ranking approach

This project deliberately does not produce a single "how strict is this
university" score, and does not rank institutions from best to worst. See
`docs/limitations.md`'s closing section and `modeling/indices.py`'s module
docstring. A ranking implies a normative judgment this project is not
positioned to make responsibly from five documents, or even from thirty:
policy language is one input into institutional practice, not a complete
picture of it, and treating a document analysis as a proxy for
institutional quality risks penalizing universities for how carefully
(or carelessly) their policy happens to be *worded*, rather than how it is
actually *practiced*.

## Risks of oversimplifying institutional policies

A 0-2 ordinal score necessarily discards nuance that a full reading of a
policy document carries. This project's mitigations: every non-zero score
is tied to a verbatim evidence passage a reader can check against the
source (never a bare number with no traceability); the coding guide
explicitly documents ambiguous cases rather than pretending scoring is
always clean; REI and PISI stay as two axes rather than collapsing into a
misleadingly precise single figure; and every dashboard page carrying
index values also carries the pilot disclaimer and (where relevant) the
rule-based-vs-human-coded distinction, so a viewer never mistakes an
early, automated, unvalidated score for a finished research conclusion.

## Data minimization

This project analyzes institutions and documents, not individual people.
No personal data about individual students, staff, or named private
individuals is collected, and this pipeline does not build profiles or
scores for any individual employee, teacher, student, or policy author —
only for documents and, in aggregate, institutions. Email addresses,
telephone numbers, and other direct personal contact information are
stripped from `cleaned_text` during text cleaning
(`processing/cleaning.py::strip_personal_contact_info`), whether or not
they were essential to the source's substance, since this project has no
use for an individual's contact details. Named public officials (e.g. a
Vice-Chancellor approving a policy) are recorded only insofar as the
source document itself names them in a public administrative capacity
(e.g. "approved by the Vice-Chancellor on [date]"), which is standard
practice for citing an official policy's provenance — retained for source
attribution only, never displayed as if it were a personal profile.

## Storage limitation

Raw collected material (PDFs, raw HTML, full extracted text, logs,
embeddings, and the local SQLite database) is kept only as long as it is
needed to run the pipeline and is never committed to the public
repository (see `.gitignore` and `docs/legal_and_compliance.md`). Once a
document's derived results (dimension scores, index values, topic
assignments) have been computed and are no longer expected to change, the
underlying raw copy can be deleted per the procedure in
`docs/legal_and_compliance.md` — the derived, non-identifying results are
what this project actually needs to keep.
