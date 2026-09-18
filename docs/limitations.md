# Limitations

This document lists what this pilot's results can and cannot support. Read
it before drawing any conclusion from the dashboard.

## Five-document pilot

The pilot contains exactly five documents, one per Nordic country. Five
data points cannot establish a stable pattern, a distribution, or a
statistically meaningful comparison of any kind. Every result should be
read as "what these five specific documents say," not as a finding about
Nordic university AI policy in general.

## No national representativeness

One university per country is not a sample of that country's higher
education system. University of Oslo's document says nothing about
whether other Norwegian universities frame AI similarly or differently;
the same applies to all five countries. Country-level rows in this
dashboard are single data points, not estimates with any statistical
uncertainty attached (there is no country-level "confidence interval" to
report — with n=1 per country, the honest thing is to show the one data
point and say plainly that it is one data point).

## English-language availability bias

This pilot only includes documents that were (a) in English and (b)
findable via search within the time available. Universities whose
AI guidance exists only in the local language, or is not indexed well
enough to find, are systematically excluded from this pilot regardless of
how substantive their actual policy is. This is a sampling bias in the
literal sense: what got collected is shaped by findability and language,
not by policy content.

## Official-translation uncertainty

For all five pilot documents, whether the collected English text is the
university's original drafting language or an official translation of a
Swedish/Norwegian/Danish/Finnish/Icelandic original could not be confirmed
from the page content alone within this pilot's scope. This is recorded
as `unknown` in every document's `translation_status` field rather than
guessed. If any of these are translations, subtle rhetorical or
legal-register choices in the original could differ from the English
version's, which would affect the qualitative reading of a document
without affecting REI/PISI's dimension-based scoring, which reads for
substance rather than phrasing style.

## Single-coder limitation

The pilot's human coding (once completed — see `docs/methodology.md`) has
exactly one coder. No inter-coder reliability can be computed or claimed.
An intra-coder check (the same coder, recoding after a time interval)
tests only whether that one coder is internally consistent with
themselves — it says nothing about whether a different coder, applying the
same guide, would reach the same scores. Coder-specific interpretive
tendencies (e.g. a systematic leniency or strictness in borderline cases)
cannot be detected or corrected for with a single coder.

## Document-type heterogeneity

The five pilot documents are not the same kind of document: Lund's is an
institution-wide policy (staff and students), Oslo's and Aarhus's are
student-facing guidance, Aalto's and Reykjavik University's are
teaching-and-learning guidance with an examination-regulation component.
Comparing REI/PISI across countries in this pilot therefore partially
conflates *country* with *document type* — a country's document might
score differently not because that country's universities are more or
less restrictive, but because that particular document type tends to be
more procedural (e.g. exam regulations) or more general (e.g. broad
institutional policy). This confound is only resolved at scale, when each
country has multiple document types represented.

## Policy volatility

Several of the pilot's source documents were approved or revised very
recently (Lund: approved December 2025; Reykjavik University: revised May
2026). Generative AI policy is an actively moving target at these
institutions. A document collected today may already be out of date by
the time this is read. Hash-based change detection
(`utils/text_hashing.py`, `processing/deduplication.py::has_content_changed`)
exists specifically so re-collection can detect this, but it requires
someone to actually re-run collection periodically — nothing in this
pilot does that automatically.

## BERTopic small-corpus instability

The topic model fit on this pilot's ~17 chunks across 4 documents is not
stable or generalizable — `modeling/bertopic_pipeline.py` enforces a
minimum document/chunk count before attempting a model at all, and every
report and dashboard page describing topic output labels it
"EXPERIMENTAL." Re-running the same pipeline with a different random seed
or a slightly different chunk size on this same small corpus could well
produce different topic boundaries. Topic modeling becomes more meaningful
as the corpus grows toward the full 30+ university target.

## Public-document availability bias

This project can only ever see what a university chooses to publish
publicly, in a place a web search or a systematic crawl can find. A
university with substantive internal or faculty-intranet AI guidance that
isn't public is invisible to this project — its absence from the dataset
says nothing about whether that university has a policy, only that it
doesn't have one that's publicly discoverable in the way this project
looks for it.

## Sandbox retrieval note (this specific pilot build)

The initial build of this pilot ran inside a network-restricted sandbox
that could not reach arbitrary university websites. Four documents' raw
text was obtained via a one-time substitute retrieval step, and Lund
University's PDF could not be retrieved at all in that environment (see
`data/raw/pilot_sandbox_retrieved/README.md` and
`outputs/reports/collection_audit.md`). This is a limitation of *this
specific build environment*, not of the project's own collection code,
which is ordinary `requests`-based Python and will work normally from any
machine with regular internet access. As of this project's compliance
correction, those four retrieved documents' full text is kept on disk but
is **no longer tracked in git** (see `docs/legal_and_compliance.md`) —
no explicit redistribution license has been confirmed for any of the five
pilot sources.

## Lund University: collection pending, not analyzed

Lund University's PDF has never been successfully collected in this
project. It is shown on the Nordic Map as a selected pilot institution
(it was one of the five sources chosen for this pilot), but its
analytical status is, and must remain, **"collection pending"** until its
PDF is actually retrieved from the official source — never fabricated,
never summarized in its place, and never given an automated or
human-coded index value without the complete document text. See
`docs/legal_and_compliance.md` ("Never fabricates or summarizes text in
place of a genuine extraction failure") and the collection audit log.

## What this project does not claim

This project does not rank institutions from "best" to "worst," does not
produce a single combined quality score, and does not claim that a high
REI score means an institution is bad for students or that a high PISI
score means it is good. REI and PISI are independent, descriptive axes.
The whole point of keeping them separate is that a university can score
highly on both, and the pilot's own rule-based results already show this:
Reykjavik University's document scores comparatively high on both axes at
once, which is a *finding to describe*, not an inconsistency to resolve.
