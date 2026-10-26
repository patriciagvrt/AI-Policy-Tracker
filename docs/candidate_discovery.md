# Policy-source candidate discovery (Phase 2)

## What this stage does, and does not do

`scripts/discover_policy_candidates.py` searches each institution's own
official domain (from `config/institutions_full.csv`) for pages and PDF
documents that *might* be its generative-AI guidance, and writes what it
finds to `data/candidates/source_candidates.csv` with a transparent,
explainable relevance score.

**Discovery finds candidates. It does not select sources.** No candidate
row is ever written to `config/sources_full.csv`, and no candidate is
automatically treated as approved, however high its relevance score --
that is a deliberate design constraint, not an oversight (see
`score_candidate` in `src/nordic_ai_policy_tracker/discovery/candidate_discovery.py`,
which never ranks a candidate as "the" answer, only as one data point for a
person to look at). Discovery also never touches `data/processed/policy_tracker_full.db`
-- database population happens at a later, separate collection stage, once
a human has chosen real sources.

## The human-review step (required)

Adding a document to this study means:

1. Open `data/candidates/source_candidates.csv` (sorted by
   `relevance_score` descending) and the matching audit report under
   `outputs/reports/full_study/`.
2. For each institution, open the highest-scoring candidates yourself and
   confirm the document is genuinely that institution's AI guidance --
   not a news article that mentions AI, not a course syllabus for one
   class, not a page that merely links to a policy hosted elsewhere.
3. Check `terms_url` / licensing the way the rest of this project already
   does for pilot sources (see `docs/legal_and_compliance.md`).
4. Only then add a row to `config/sources_full.csv` by hand, following the
   schema in `docs/data_dictionary.md`.

A high relevance score means the URL, title, and text preview contain
several of the search terms below -- it is a hint about where to look
first, never a verdict. A human researcher fluent in Icelandic should
also review the Icelandic search-term list in
`src/nordic_ai_policy_tracker/discovery/search_terms.py` before treating
Icelandic-language discovery results as complete; that list is a
best-effort starting set, not reviewed by a fluent speaker as part of this
implementation.

## How discovery finds candidates

For each institution (filtered by `--country`, e.g. `Iceland`):

1. **robots.txt** is fetched and parsed first. A URL robots.txt disallows
   is never fetched -- not even to check its title or content. It is
   never written to the candidates CSV either (a zero-score, unfetched
   placeholder row has no evidence behind it and has no business being
   mistaken for a real candidate); it is instead recorded, clearly marked
   as a non-candidate, in the audit report's "non-candidate portals"
   list -- see "Curated additional official domains and non-candidate
   portals" below.
2. **Sitemaps** declared in robots.txt (or a `/sitemap.xml` fallback) are
   fetched, including one level of `<sitemapindex>` nesting, up to a
   bounded number of sitemap files per institution.
3. A **single-hop homepage link crawl** supplements the sitemap (for
   institutions whose sitemap is missing, stale, or incomplete) -- this is
   not a general crawler; it only looks at links found on the homepage
   itself, and only after confirming robots.txt allows fetching the
   homepage.
4. Discovered URLs are **normalized and deduplicated** (case, trailing
   slash, default port, and fragment differences collapse to one URL).
5. Each remaining same-domain URL is pre-filtered by a quick check of
   whether its own path looks relevant (so, e.g., a cafeteria-menu page is
   never even fetched), then capped at `--max-pages-per-institution`
   (default 25) -- discovery is deliberately bounded, not a full crawl.
6. Each surviving URL is fetched **politely**: a configurable delay
   between requests, a clear identifying user agent, and the same
   403/429-means-stop-immediately rule already used by
   `src/nordic_ai_policy_tracker/collection/crawler.py` (this project
   never retries past an access-denied or rate-limit response).
7. HTML pages and PDF documents are both handled, reusing the existing
   `html_extractor` / `pdf_extractor` modules.
8. Each fetched page is scored (see below) against the search terms in
   `search_terms.py` and written to the candidates CSV.

## The relevance score

The score is a small, fully documented point formula -- **not** BERTopic,
not an embedding similarity, not REI/PISI (those are pilot indices for
already-selected documents, not a discovery tool):

```
score = 3 * (number of search terms matched in the page title)
      + 2 * (number of search terms matched in the URL path)
      + 1 * (number of search terms matched in the first ~500 characters
             of extracted text, capped at 5)
      + 1 if the document is a PDF, else 0
```

A reviewer can recompute any candidate's score by eye from the
`matched_terms` and `content_type` columns in the CSV -- there is no
hidden model call, no training data, and no randomness in this
calculation.

## Search terms

English terms (primary list) and a best-effort Icelandic list cover:
artificial intelligence, generative AI, ChatGPT, large language models,
teaching and learning, assessment and examinations, academic integrity,
student guidance, staff guidance, and university/AI policy. See
`src/nordic_ai_policy_tracker/discovery/search_terms.py` for the exact
lists.

## Output: `data/candidates/source_candidates.csv`

One row per (institution, candidate URL) pair, sorted by relevance score
descending. Columns:

| Column | Meaning |
|---|---|
| `institution_id`, `institution_name`, `country` | From `config/institutions_full.csv` |
| `candidate_url` | URL as discovered (sitemap entry, homepage link, or the homepage itself) |
| `final_url` | URL actually returned after redirects (`requests`' `response.url`) |
| `page_title` | Extracted `<title>` (HTML only; blank for PDFs) |
| `content_type` | `html` or `pdf` |
| `discovery_method` | `sitemap`, `homepage_link_crawl`, or `homepage` |
| `matched_terms` | Semicolon-separated search terms found in the URL, title, or text preview |
| `relevance_score` | See formula above |
| `text_preview` | First ~500 characters of extracted text (for quick eyeballing without opening the URL) |
| `robots_allowed` | `True` / `False` / blank (unknown) |
| `http_status` | HTTP status of the fetch, or blank if robots.txt blocked the fetch |
| `checked_at` | UTC timestamp of the check |

## Audit report

Each run also writes a markdown audit report (default
`outputs/reports/full_study/candidate_discovery_report_<country>.md`)
listing, per institution: the domain searched, whether robots.txt was
reachable, which sitemaps were declared and which were actually fetched,
how many sitemap/homepage URLs were found, how many duplicate URLs were
removed, how many requests were attempted, how many candidates were
found, and any errors -- plus a combined table of every candidate's score
across all institutions searched in that run.

## Curated additional official domains and non-candidate portals

Added at the correction stage following the 26 October 2026 live Iceland
run, which surfaced that the University of Iceland returned zero
candidates despite relevant material existing on `setberg.hi.is`.

**Accepting a discovered subdomain is not the same as knowing that the
subdomain exists.** Before this fix, a genuine subdomain only entered
discovery's search scope if it was organically found via the single-hop
homepage link crawl. `setberg.hi.is` is not linked from `hi.is`'s own
homepage -- institutions commonly run a dedicated AI-guidance portal as a
standalone destination, announced through some other channel (email,
internal wiki, a conference talk) -- so no amount of homepage-link-
crawling or sitemap-following starting from the institution's own
homepage could ever have found it.

The fix is `additional_official_domains`, an optional, semicolon-
separated column on `config/institutions_full.csv` (see
`config/README_full_study_registry.md`): a curated list of extra
hostnames that a human researcher has verified belong to the institution.
Discovery always searches every domain listed there, in addition to
`official_website` and whatever subdomains it finds organically --
`setberg.hi.is` is populated for `hi_is` as the first such entry. A
domain never becomes searchable just by being named here, though: it
must also pass the same registrable-domain check (`is_same_domain`) used
for organically-found subdomains, which also rejects a deceptive
lookalike domain (e.g. `hi.is.evil.example`).

**Sitemap URLs are validated before they are ever requested.** The same
live run also showed discovery attempting invalid sitemap URLs such as
`http://default/sitemap.xml?page=1` -- a CMS/reverse-proxy
misconfiguration on the institution's own server, returning its internal
default-vhost name when generating paginated sitemap-index entries.
Every sitemap URL (including nested `<sitemapindex>` entries) is now
checked for an `http`/`https` scheme and for being inside the
institution's approved domain scope (`official_website`,
`additional_official_domains`, or a genuine subdomain of either) before
`requests.get()` is ever called on it. This is a generic domain-scope
check, not a hardcoded "default" special case -- `default` is rejected
because it never matches any Nordic institution's registrable domain, the
same way any other out-of-scope host would be. Rejected URLs are recorded
separately as "sitemap URLs rejected as invalid/out-of-scope", and a
sitemap URL that *is* in scope but still fails to fetch (timeout,
connection error, non-200 status) is recorded separately again as a
"sitemap fetch warning" -- both counts are reported per institution and
in the audit report's totals, distinctly from page-fetch `errors`, so a
report can never again say "Errors: 0" while sitemap-fetch problems had
in fact occurred.

**Robots-disallowed portals are audit-only, not candidates.** A URL that
robots.txt disallows (for example a login-gated student portal like
`ugla.hi.is`) was previously written into the candidates CSV as a
zero-score, never-fetched placeholder row "for transparency" -- but a row
with no title, no text, and no term evidence either way has no business
being mistaken for a real candidate. These are now recorded only in the
audit report, under a "non-candidate portals" list, each entry naming the
URL, how it was discovered, and the reason it was excluded (currently
always "robots.txt disallowed -- not fetched").

## Job/vacancy classification

Also added at the correction stage: the 26 October 2026 live run showed a
University of Akureyri job advertisement ("Laust starf: Þróunarstjóri
gervigreindar" -- an AI development officer posting) categorized
"guidance", because it matched a strong AI term with no more specific
category rule catching it first. `classify_category` now checks a small
set of Icelandic and English job/vacancy URL segments and title phrases
(`laust-starf`, `atvinna`, `vacanc`, `career`, "job vacancy", etc. -- see
`JOB_URL_SEGMENTS` / `JOB_TITLE_SIGNALS` in `candidate_discovery.py`)
before falling back to "guidance", and a job posting's score is penalized
(mirroring the existing news penalty) but not excluded -- it remains a
discoverable, labeled candidate, not a hidden one.

## Dry-run / fixture mode (no live network required)

`--fixtures-dir <path>` runs the entire pipeline against local files
instead of making real HTTP requests -- see
`tests/fixtures/discovery/` for the expected layout (a directory per
domain, containing `robots.txt`, `sitemap.xml`, and one file per page
path; a clean/extensionless sitemap URL is looked up as `<path>.html`).
This is how `tests/test_candidate_discovery.py` verifies the whole
pipeline without depending on any live website, and it is also how this
implementation was validated in an environment whose outbound network
access is restricted to an allowlist that does not include individual
Icelandic university domains (see the Known limitations section below and
the final validation report for this stage).

## Known limitations

- The Icelandic search-term list is a best-effort starting set and has
  not been reviewed by a fluent Icelandic speaker as part of this
  implementation.
- The homepage link crawl is a single hop; a policy page linked only from
  a page two or more clicks from the homepage, with no sitemap entry,
  will not be found.
- Discovery has only been validated end-to-end against local fixtures in
  this environment (see the limitations note above); a live run against
  real Icelandic university websites should be re-verified from a
  normally-networked machine before being relied on operationally.
- This first implementation has only been exercised for `--country
  Iceland`; running it for other countries should work (the logic is not
  Iceland-specific) but has not itself been validated end-to-end yet.
