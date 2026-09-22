# AI Policy Tracker — Pilot Analysis

**Author:** Patricia Cruz
**Date:** 2026-09-19
**Status:** Pilot report, human-coded results authoritative; automated and topic-model results exploratory
**Public copy note:** This file is the public, tracked copy of the project's generated pilot report. It is published here unchanged, byte-for-byte identical to `outputs/reports/pilot_analysis.md` (the local, git-ignored source of record produced by the project's reporting step). References below to `outputs/reports/pilot_analysis.md` describe that generated source file, not a separate document.

## Pilot overview

This report presents the results of a pilot study covering five European universities, one per Nordic country (Finland, Denmark, Sweden, Iceland, Norway). The pilot tests the full analytical pipeline end to end — document collection, text cleaning, human coding against a fixed dimension scheme, an automated keyword-based comparison, and exploratory topic modeling — before the project is extended to a larger corpus. The pilot sample is not representative of any national higher-education system; every finding in this report describes these five documents only.

## Research goal and questions

The AI Policy Tracker project examines how European university AI-use policies balance two independent concerns: restricting and enforcing rules around AI use, and supporting staff and students in using AI productively. The project's guiding questions are:

1. To what extent do university AI policies emphasize restriction, enforcement, and compliance risk, as measured by a Restriction and Enforcement Index (REI)?
2. To what extent do the same policies emphasize pedagogical integration and support, as measured by a Pedagogical Integration and Support Index (PISI)?
3. Are these two orientations independent of one another, or does a policy's emphasis on one predict its emphasis on the other?
4. What thematic patterns emerge across policies when analyzed with unsupervised topic modeling, and how do these compare with the manually defined coding dimensions?

This pilot addresses these questions on a small scale, as a methodological validation step ahead of the full 30+ university study.

## Corpus and data collection

The pilot corpus consists of one publicly available AI-use policy or guidance document from each of five universities:

| University | Country | Document type | Word count | Source format |
|---|---|---|---|---|
| Aalto University | Finland | Teaching and learning guidance | 626 | HTML |
| Aarhus University | Denmark | Student and examination guidance | 744 | HTML |
| Lund University | Sweden | Institution-wide policy | 1,378 | PDF |
| Reykjavik University | Iceland | Teaching and learning guidance and examination regulation | 1,248 | HTML |
| University of Oslo | Norway | Student guidance | 420 | HTML |

All five documents were collected successfully through the project's live collection pipeline: 0 collection failures, 0 exact duplicates, and 29 text chunks produced in total. All five analyzed texts were detected as English with confidence 1.00. However, automatic language detection cannot determine whether English is the document's original language or whether the text is an official translation. Original-language and official-translation status therefore remain uncertain where they were not explicitly confirmed by the source. Document type varies across the five sources (institution-wide policy, teaching guidance, student guidance, and examination guidance), which is itself an important variable in reading the results below.

## Human-coded REI/PISI results

The results below are the human-coded index scores — the pilot's single coder's (Patricia Cruz) complete annotation of every dimension for every document — normalized to a 0–100 scale within each axis. REI and PISI are conceptually defined and calculated as separate axes. A score on one axis does not mechanically determine a score on the other. However, this five-document pilot does not contain enough observations to assess whether the two indices are statistically associated. Neither axis is a measure of policy quality.

| University | Human REI | Human PISI |
|---|---:|---:|
| Aalto University | 42.9 | 59.1 |
| Aarhus University | 57.1 | 36.4 |
| Lund University | 21.4 | 54.5 |
| Reykjavik University | 92.9 | 72.7 |
| University of Oslo | 42.9 | 50.0 |

Across the pilot's five documents, REI values range from 21.4 to 92.9 and PISI values range from 36.4 to 72.7, with substantial variation on both axes. These figures are descriptive, not evaluative: they are not a ranking of the five universities, and this report deliberately avoids terms such as "best," "worst," "highest-performing," or "most advanced," since REI and PISI describe how a document is framed, not how well an institution manages AI use. Each score describes only the single document collected for that institution, coded against the same 18 dimensions (7 for REI, 11 for PISI); document type is often a more informative lens for reading a given score than the institution or country it came from, as the pattern below illustrates.

Aalto University's `equity_accessibility_inclusion` dimension is now scored 1 (mentioned) rather than 0, reflecting the coder's current annotation. This raises Aalto's PISI total from an earlier reading of 54.5 to the current 59.1, and it changes a claim made in an earlier version of this analysis: `equity_accessibility_inclusion` is absent (score 0) in four of the five documents, not all five.

With only five documents, this pilot can describe the specific REI/PISI configuration of each document -- for example, that Reykjavik University combines a comparatively high REI score with a comparatively high PISI score, or that Lund University combines a comparatively low REI score with a moderate-to-high PISI score. It cannot test whether REI predicts PISI, or estimate a correlation between them: five heterogeneous documents, differing in document type, length, and institution, provide far too small and too uncontrolled a sample for any correlation, prediction, or general relationship between the two axes to be inferred. Any such claim would require a substantially larger and more systematically sampled corpus, as outlined in Next steps for scaling to 30+ universities below.

## Cross-university patterns

Examining the 18 individual dimensions, rather than only the two composite scores, surfaces patterns that the totals conceal.

**Consistent across all five documents.** `permitted_encouraged_use` (PISI) scores 2 (emphasized) in every document in this pilot: each document affirmatively permits or encourages some use of AI rather than imposing a blanket restriction. Read alongside the REI values above, this indicates that even the documents that emphasize control most strongly on other dimensions are regulating how AI may be used, not prohibiting it outright.

**A near-universal gap, with one exception.** `equity_accessibility_inclusion` (PISI) scores 0 (absent) in four of the five documents. Aalto University's document is the exception, scoring 1 (mentioned) on this dimension. Equity and accessibility considerations in relation to AI use remain largely undeveloped across this pilot's documents, but it is no longer accurate to describe this dimension as absent from all five.

**Linked to document type.** Two dimensions split cleanly along document type rather than along any single institution:

- `teaching_integration` (PISI) scores 2 in the two documents whose type is teaching and learning guidance (Aalto, Reykjavik) and 0 in the two documents that are student- or examination-focused (Aarhus, Oslo).
- `assessment_examination_control` (REI) scores 2 in the two documents whose type includes examination regulation specifically (Aarhus, Reykjavik) and 0 in the other three.

Document type appears to account for at least part of what distinguishes this pilot's five documents from one another — a pattern that should be tested directly, not assumed, once the study is extended to more institutions and to more than one document type per institution.

## Comparison with automated exploratory hints

Alongside the human-coded index, the pipeline produces an automated "hint" score for each dimension, generated by a rule-based keyword and negation-aware pattern matcher (see Methods and validation below). These automated scores are exploratory only: they are intended to surface candidate evidence for a human coder to review, never to stand as a validated REI or PISI result in their own right, and they are reported here strictly as a point of comparison with the human-coded results above.

The two methods diverge substantially, most visibly on PISI: for example, Aalto's and Lund's automated PISI hints (13.6 and 9.1, respectively) are far below their human-coded PISI scores (59.1 and 54.5). This divergence is a limitation of the automated method, not evidence against the human coding. The keyword matcher can only recognize a fixed list of literal phrases per dimension, together with basic negation handling (for example, distinguishing "AI is not allowed" from "AI is allowed"). It systematically misses:

- **Paraphrase.** Most real policy text expresses a concept without using one of the configured keyword phrases verbatim, so substantively relevant sentences are simply invisible to the matcher.
- **Contextual evidence.** A dimension can be supported by the surrounding argument of a passage rather than by any single matched phrase, which the matcher cannot assess.
- **Links to institutional support.** References to a writing centre, a helpdesk, or a staff-development office may indicate student or staff support without containing any of the dimension's specific keywords.
- **Strong evidence expressed without the configured keywords.** A sentence can make a dimension's point emphatically while never using the literal wording the keyword list anticipates, in which case the automated score under-counts it.

A secondary, smaller contributor is the automated scoring rule itself, which maps zero keyword matches to a score of 0, one match to 1, and two or more matches to 2; a single strongly worded sentence can therefore cap out at 1 even where a human coder would reasonably score the same passage 2. Together, these two effects — missed paraphrase and a coarse match-count rule — account for the gap between the automated and human results observed in this pilot, and they are the reason the human-coded results, not the automated hints, are treated as this report's substantive findings.

## Methods and validation

**Processing pipeline, in plain language.** Each collected document is cleaned of navigation elements, boilerplate, and formatting artifacts, and personal contact information (email addresses and phone-number-shaped sequences) is automatically redacted as a data-minimization safeguard, since this project analyzes institutions and documents rather than individuals. Each document is then checked with automatic language detection before any scoring; all five documents in this pilot were detected as English with full confidence (1.00). This detection step identifies the language of the analyzed text only; it does not establish whether English is a document's original language or whether a page is an official translation. The cleaned text is split into smaller chunks for downstream analysis, producing 29 chunks across the 5 documents. Two independent analytical layers are then applied on top of this text: a rule-based, negation-aware keyword matcher, used only to propose exploratory candidate evidence (discussed above); and, for the topic-model analysis described in the next section, semantic sentence-transformer embeddings that group chunks into topics. Neither automated layer produces the REI or PISI scores that anchor this report; those scores come from the human coder's own reading of each source document against the 18 dimensions defined in the project's coding guide.

**Data quality.** All 5 targeted documents were collected successfully: 0 failures, 0 duplicates, 29 chunks extracted, and no missing-data warnings. All five were collected through the project's live HTTP collection pipeline (no browser-automation fallback was required for this pilot).

**A confirmed code fix.** An earlier version of the project's database layer inserted new scoring rows without first removing any prior row for the same document, dimension, and coder — so re-running the automated scoring pipeline, an ordinary and expected part of the workflow, silently duplicated rows rather than replacing them. This was the exact cause of an earlier dashboard display issue in which each automated component score appeared twice; the dashboard's own display logic was correct throughout, and was faithfully rendering duplicated underlying rows. The database layer now removes any existing row with the same identity immediately before inserting a new one, so re-running the pipeline is safe to repeat, and this behavior is covered by automated tests. The live database was backed up before the fix was applied, then deduplicated using only the confirmed-duplicate rows; the human-coded annotations and human index results were left untouched and were verified unchanged before and after.

## NLP and BERTopic results

This section reports the project's exploratory topic-modeling analysis. It is explicitly experimental: it was fit on only 5 documents and 29 chunks, far too few for the resulting topics to be considered stable or generalizable, and topic assignments are computed entirely independently of the REI/PISI scores above — they are never used as evidence for them.

The pipeline that produces this analysis, in plain language, consists of: collecting each university's HTML page (or, for Lund University, its published PDF policy) and extracting its text; cleaning that text and removing personal contact information; detecting and confirming the document's language; dividing the cleaned text into 29 smaller chunks; generating semantic sentence-transformer embeddings (`all-MiniLM-L6-v2`) for each chunk; clustering those embeddings into topics using BERTopic, which also extracts each topic's representative keywords using class-based TF-IDF (c-TF-IDF); and, finally, a human interpretation step in which the researcher proposes a provisional, unconfirmed label for each topic based on its automatically extracted keywords.

Using this pipeline (report: `outputs/reports/topic_model_report.md`, topic status: experimental), the current, authoritative run — using the configured `all-MiniLM-L6-v2` sentence-transformer embeddings — found 3 topics and 3 outlier chunks across the corpus's 29 total chunks:

| Topic | Chunks | Automatic keywords (c-TF-IDF) | Provisional manual label |
|---|---|---|---|
| 0 | 13 | use ai, students, teaching, student, learning, course, assessment, artificial intelligence | "Responsible and safe AI use" |
| 1 | 9 | generative, university, use generative, development, responsible, policy | "Institutional support and AI literacy" |
| 2 | 4 | gai, exam, allowed, use gai, declaration, feedback | "Assessment rules and AI disclosure" |

Three chunks did not fit any topic and were left as outliers rather than forced into one. All three provisional manual labels are researcher interpretations proposed from the automatic keywords; none has been confirmed, and the project's dashboard keeps automatic and manual labels structurally separate so that one is never mistaken for the other.

**Institution-dominance caveat.** Topics 1 and 2 are institution-specific and must not be read as cross-university Nordic themes: 100% of Topic 1's 9 chunks come from Lund University alone (its institution-wide policy document), and 100% of Topic 2's 4 chunks come from Aarhus University alone (its student and examination guidance document). Each more likely reflects that one institution's document — its particular writing style, structure, or source vocabulary — than a theme shared across the corpus. Topic 0 is the only one of the three that draws on multiple institutions, spanning all four other universities (Aalto, Aarhus, Reykjavik, Oslo), but it is not evenly shared: Reykjavik University alone contributes 53.8% of Topic 0's chunks. Even Topic 0, while the closest of the three to a genuine cross-institution theme, should therefore be read as influenced by Reykjavik's framing rather than as an equally weighted composite of all five universities.

## Limitations

- **Small, non-representative sample.** The pilot covers only five universities, one per Nordic country and one document per institution. It is not a representative sample of Nordic or European higher-education AI policy, and its findings should not be generalized beyond this specific set of five documents.
- **Different document types across institutions.** The five documents differ in type (institution-wide policy, teaching guidance, student guidance, examination guidance), which confounds institution-level and document-type-level explanations for the patterns observed; see Cross-university patterns above.
- **English-language documents and translation uncertainty.** All five documents were detected as English by automatic language detection, with confidence 1.00. This detection confirms only the language of the analyzed text; it does not establish whether English is the original language of each document or whether the analyzed page is an official translation, and this pilot does not independently confirm original-language or official-translation status for any of the five documents. This uncertainty would also apply, and grow, in a larger corpus including non-English source documents.
- **Single human coder.** All human-coded scores in this pilot come from one coder. No inter-coder reliability statistic can be computed yet, and a second coder's reading of the same documents could differ on individual dimension scores, particularly on more interpretive dimensions such as `responsible_use` and `human_oversight_responsibility`.
- **Automated scoring is a screening aid only.** As detailed above, the keyword-matching method under-detects paraphrased language by design; it is not a validation of, nor evidence against, the human-coded results.
- **Experimental topic-model results.** With only 29 chunks, 3 topics is close to the practical floor for meaningful clustering, and two of the three topics are already flagged as institution-specific. An institution-specific topic may reflect that source's particular document type, writing style, or vocabulary rather than a pattern shared across Nordic universities more generally.
- **Policies may change over time.** Each document reflects the state of an institution's published policy at the time it was collected; institutional AI policies in this domain are being actively revised, and a re-collected document at a later date may differ from the version analyzed here.

## Next steps for scaling to 30+ universities

Extending this pilot to the project's full target of more than 30 European universities will require several concrete steps beyond simply collecting more documents:

1. **Stratified institution selection.** Select institutions using an explicit sampling strategy (for example, by country, institution type, and size) rather than convenience sampling, so that comparisons across countries and institution types are methodologically defensible.
2. **Multilingual document handling.** Extend the collection and cleaning pipeline to handle non-English source documents, including translation and a documented approach to translation-quality uncertainty, since this pilot's all-English corpus does not exercise that part of the pipeline.
3. **Harmonized document types.** Establish a standardized document-type taxonomy at the point of collection (for example, distinguishing institution-wide policy from teaching guidance, student guidance, and examination regulation) and, where possible, collect more than one document type per institution, so that document-type effects can be separated from institution-level effects rather than confounded as in this pilot.
4. **A second human coder and inter-coder reliability.** Add a second coder and conduct a formal inter-coder reliability check — a shared subset of documents coded independently by both coders, compared using a statistic such as Cohen's kappa — before treating any single coder's scores as the project's definitive measure. This also enables the `validated_rei`/`validated_pisi` indices already supported by the project's data schema, which require a second coding round and remain unpopulated in this pilot.
5. **Version tracking.** Record a retrieval date and, where feasible, a content hash or version identifier for each collected document, so that a future re-collection of the same institution's policy can be distinguished from the version originally analyzed, given that policies may change over time.
6. **Rerunning BERTopic on a larger corpus.** Once a substantially larger number of chunks is available, rerun the topic model; a larger, more diverse corpus is required before topic assignments can be assessed for stability and read as genuine cross-institution themes rather than artifacts of a small, institution-imbalanced sample.

## Consistency checklist

This report was generated directly from the current state of the project's files. No document collection, processing, index calculation, or BERTopic run was repeated to produce it, and no SQLite database, annotation CSV, or Parquet file was modified while preparing it.

- Documents collected successfully: 5
- Text chunks: 29
- Documents with complete human coding: 5
- Human-coded dimension scores: 90
- Human-coded index results: 10
- BERTopic topics: 3
- BERTopic outlier chunks: 3
- Aalto University human PISI: 59.1

| University | Human REI | Human PISI |
|---|---:|---:|
| Aalto University | 42.9 | 59.1 |
| Aarhus University | 57.1 | 36.4 |
| Lund University | 21.4 | 54.5 |
| Reykjavik University | 92.9 | 72.7 |
| University of Oslo | 42.9 | 50.0 |

**Files read to produce this report:** `data/processed/policy_tracker.db` (human-coded `dimension_scores` and `index_results` tables, read-only), `outputs/reports/topic_model_report.md`, `outputs/reports/data_quality_report.md`, `outputs/reports/collection_audit.md`, `docs/coding_guide.md`, `docs/methodology.md`, `config/coding_dimensions.yaml`, `src/nordic_ai_policy_tracker/processing/cleaning.py`, and the project's prior pilot analysis document.

**File changed:** `outputs/reports/pilot_analysis.md` only. The SQLite database, Parquet files, human annotations, topic assignments, and topic labels were not modified, and no script was rerun.

**Underlying data availability.** The 90 human-coded dimension scores
behind the REI/PISI table above are published in full, in reproducible
form, at `data/annotations/pilot_scores_public.csv` (recalculating REI and
PISI from that file alone reproduces the table above exactly). The
evidence passages the coder cited for each non-zero score are not
published, because summed across a document's 18 dimensions they can
reconstruct most or all of a source document's text, and redistribution
rights are not yet confirmed for any of the five pilot sources; see
`docs/annotation_data_release.md`.
