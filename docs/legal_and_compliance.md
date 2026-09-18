# Legal and Compliance

This document is the single place that spells out this project's
collection-time legal procedure: what is checked before a source is
scraped, what this project will never do to get past a source that says
no, what stays out of version control, what may be redistributed, and how
raw copies are eventually deleted. It complements, and should be read
alongside, `docs/ethics.md` (the broader ethical posture),
`docs/methodology.md` (how documents are turned into scores), and
`docs/limitations.md` (what the results can't support).

## Before collection: robots.txt and terms of use

Two separate checks happen (or are meant to happen — see "What is not yet
automated" below) before a source is ever fetched:

1. **robots.txt** (`collection/robots.py`). The collector's own IS an
   automated check: `collection/crawler.py::collect_one` calls
   `robots.is_allowed()` before requesting the policy document itself, and
   a `False` result (robots.txt disallows the collector's user agent)
   causes the collector to skip that source entirely
   (`collection_status=SKIPPED_ROBOTS_DISALLOWED`), never override it.
   `None` (robots.txt could not be retrieved or parsed) is recorded
   honestly as unknown, not silently treated as permission.

2. **Terms of use / text-and-data-mining (TDM) rights.** robots.txt says
   what a crawler may *fetch*; it says nothing about what may be
   *redistributed* or *mined*, which is a separate legal question that
   requires an actual human reading a site's terms-of-use page. This
   project does not implement automated terms-of-use parsing (see below) —
   every `PolicyDocument` and `University` record instead carries
   `terms_checked` (default `false`), `terms_url` (default unset), and
   `legal_review_status` (default `pending`) fields precisely so that the
   absence of a human legal check is visible in the data itself, not
   silently assumed away. A source whose `legal_review_status` is set to
   `restricted` should not be collected at all going forward.

### What is not yet automated

Automated terms-of-use / TDM-reservation detection is **not implemented**
in this pilot. `PolicyDocument.tdm_reservation_detected` therefore
defaults to `None` (not checked) for every collected document rather than
a guessed `True`/`False`. Before any future collection run redistributes
document text beyond short cited excerpts, a human should visit each
source's terms-of-use page, record the outcome via `terms_checked=True`,
`terms_url=<the page checked>`, and an appropriate `legal_review_status`,
and note anything relevant in `copyright_notice`/`license_note`.

## What this project never does

- **Never bypasses authentication, CAPTCHAs, rate limits, or other access
  controls.** The collector only ever requests a source's publicly
  reachable URL with a normal, identifying `User-Agent`
  (`config/settings.yaml::collection.user_agent`) — it does not attempt to
  log in, solve a CAPTCHA, spoof headers to evade a block, or otherwise
  work around a site telling it no.
- **Never retries after a 403 (Forbidden) or 429 (Too Many Requests)
  response.** `collection/crawler.py::_polite_get` treats these two status
  codes as a hard stop: the very first 403/429 raises `AccessDeniedError`
  immediately, with no backoff-and-retry loop of any length. Retrying a
  response that explicitly denies access would look exactly like the kind
  of access-control bypass this project refuses to attempt. The source is
  recorded as a genuine collection failure
  (`collection_status=FAILED`), never worked around.
- **Never fabricates or summarizes text in place of a genuine extraction
  failure.** If a source's actual text cannot be obtained (network
  failure, access denial, or — as with Lund University's PDF in this
  pilot's original sandbox build — a fetch tool returning a
  model-generated summary instead of the document's real sentences), the
  document is recorded as `collection_status=FAILED`
  (or, for a source still awaiting collection, `PENDING`), never populated
  with placeholder, summarized, or approximated text. See
  `docs/limitations.md` for the Lund case specifically.

## What stays out of public Git tracking

`.gitignore` excludes the following from version control:
`data/raw/` (all downloaded PDFs, raw HTML, and full extracted text),
`data/interim/`, every `*.db`/`*.sqlite`/`*.sqlite3` (the local SQLite
database), every `*.pdf`/`*.html` file anywhere in the repository (narrow,
explicit exceptions exist only for small synthetic test fixtures under
`tests/fixtures/`), every `*.parquet` file (chunk/embedding/topic data),
`logs/`, `models/` (any locally cached embedding model), `.streamlit/`,
and the usual virtual-environment/cache directories.

This means: a fresh clone of this repository, before any collection
script has been run, contains no raw policy text, no database, and no
embeddings — only code, configuration, documentation, and (for this
pilot's own reproducibility) the annotation template and derived result
files the pipeline itself produces into version-controlled locations.

**Note on this pilot's earlier delivery:** an earlier draft of this
repository tracked `data/raw/pilot_sandbox_retrieved/*.md` (this pilot's
substitute retrieval text for four of the five sources, used only because
the original build sandbox had no live internet access) directly in git,
as a documented exception. That exception has been **removed** as of this
compliance correction — those files are full extracted policy text, and
no explicit redistribution license has been confirmed for any of the five
sources (every document's `legal_review_status` is still `pending`). The
files themselves remain on disk (deleting them is a separate, deliberate
decision — see "Deleting raw copies" below) but are no longer tracked by
git.

## Redistribution policy

Absent an explicit license confirming redistribution rights for a
specific source (`legal_review_status=reviewed_redistribution_allowed`),
this project's public repository and dashboard publish only:

- **Metadata** — title, institution, document type, intended audience,
  publication/retrieval dates, source URL, language fields.
- **Derived results** — dimension scores, REI/PISI index values (all
  three kinds — automated hints, human-coded, validated), topic
  assignments, confidence/coverage statistics.
- **Short, necessary excerpts** — a verbatim evidence passage supporting a
  specific dimension score, kept as short as needed to support that one
  score (this project's coding guide already requires short, targeted
  quotes, not block reproduction).
- **Links to the official source pages** — so a reader can read the full
  document themselves, at its authoritative source.

Full policy documents (complete PDFs, complete extracted HTML text) are
never published in the repository or the dashboard unless a specific
source's terms have been reviewed and `legal_review_status` set to
`reviewed_redistribution_allowed` for that source.

### Excerpt citation requirements

Every excerpt shown anywhere in this project (an evidence passage in the
Annotation or Document Comparison pages, a representative chunk in the
Topic Explorer) must be shown alongside: the document's title, the
issuing institution, the source URL, and the retrieval date. This is
already how `DimensionScore.evidence_passage` is displayed today (always
next to its parent document's metadata row, which carries `source_url`
and `retrieval_timestamp`) — this section makes that requirement explicit
rather than leaving it as an implementation accident.

## Deleting raw copies when no longer necessary

Once a document's derived results (dimension scores, index values, topic
assignments) have been computed and are not expected to need
recomputation from the original text, the underlying raw copy (the row's
`raw_text`, and any corresponding file under `data/raw/`) is no longer
needed for this project's ongoing operation and can be deleted:

1. Confirm the document's derived results are already persisted (i.e.
   `dimension_scores`/`index_results` rows exist referencing its
   `document_id`, or intentionally will not be recomputed).
2. Delete the corresponding file(s) under `data/raw/` for that source, if
   any exist outside the database.
3. Clear the database row's raw material — `UPDATE documents SET
   raw_text = '' WHERE document_id = ?` — while leaving `cleaned_text`,
   metadata, and all derived tables intact, since `cleaned_text` (already
   scrubbed of personal contact information — see `docs/ethics.md`) is
   what downstream processing and the dashboard actually use.
4. Record the deletion (date, reason) in a note alongside the collection
   audit, so the document's provenance trail stays complete even after
   its raw copy is gone.

This procedure is deliberately manual rather than automatic: an automatic
deletion timer could destroy the one copy of a source that later turns
out to be needed (e.g. to recheck an evidence passage after a coding
dispute), so a human decides when a document's raw copy is genuinely no
longer necessary.

## Personal-data safeguards

See `docs/ethics.md`'s "Data minimization" and "Storage limitation"
sections for the personal-data specific safeguards (email/phone stripping
in text cleaning, no individual profiling, retention of names only for
source attribution).
