# AI Policy Tracker — Pilot Analysis

2026-09-18 · @Someone

## Pilot overview

This pilot covers five universities, one per Nordic country, and tests the full pipeline end to end: collection, cleaning, human coding, an automated-hint comparison, and exploratory topic modeling. It is not a representative sample of any national higher-education system; every finding below describes these five documents only.

| University | Country | Document type | Word count |
| --- | --- | --- | --- |
| Aalto University | Finland | Teaching and learning guidance | 626 |
| Aarhus University | Denmark | Student and examination guidance | 744 |
| Lund University | Sweden | Institution-wide policy | 1,378 |
| Reykjavik University | Iceland | Teaching and learning guidance and examination regulation | 1,248 |
| University of Oslo | Norway | Student guidance | 420 |

All five were collected live and successfully (0 failed, 0 duplicates, 29 text chunks total), and all five now have complete human coding across every dimension.

Each document is scored on two independent axes, both 0 to 100:

- **REI (Restriction and Enforcement Index):** how much the policy frames AI as a compliance risk to control, penalize, or detect, across 7 dimensions (prohibition, punishment, misconduct framing, detection/surveillance, mandatory disclosure, exam control, privacy restriction).
- **PISI (Pedagogical Integration and Support Index):** how much the policy frames AI as a teaching and learning capability to develop and support, across 11 dimensions (permitted/encouraged use, AI literacy, critical evaluation, responsible use, teaching integration, student support, staff support, transparency/citation, equity, privacy awareness, human oversight).

The two axes are independent. A document can score high, low, or moderate on both at once, so REI and PISI should always be read as a pair, not a single left-right scale.

All scores in this report are the **human-coded** results, the pilot's authoritative source, unless a section explicitly says otherwise.

## REI/PISI results

All scores below are human-coded (the authoritative index), normalized to a 0–100 scale within each axis. REI and PISI are independent — a university can score high, low, or anywhere on one axis regardless of its score on the other.

| University | Country | REI (Restriction/Enforcement) | PISI (Pedagogical Support) |
| --- | --- | --- | --- |
| Reykjavik University | Iceland | 92.9 | 72.7 |
| Aarhus University | Denmark | 57.1 | 36.4 |
| Aalto University | Finland | 42.9 | 54.5 |
| University of Oslo | Norway | 42.9 | 50.0 |
| Lund University | Sweden | 21.4 | 54.5 |

Reykjavik University sits highest on both axes — its guidance is both the most restriction/enforcement-oriented and the most pedagogically supportive of the five, which is consistent with it being the only document type combining teaching guidance with examination regulation. Aarhus pairs the second-highest REI score with the lowest PISI score: its policy leans toward rules and control with comparatively little support content, matching its student/examination-guidance document type. Lund is the mirror image of Aarhus — the lowest REI score in the pilot alongside a mid-to-high PISI score — indicating a policy that emphasizes support and guidance over restriction. Aalto and Oslo land close together in the middle of both axes.

These five scores are not a ranking of "stricter" versus "friendlier" universities in any general sense — they describe only the text of the one document collected for each institution, coded against the seven REI and eleven PISI dimensions defined above.

## Cross-university patterns

Looking across the 18 dimensions (7 REI + 11 PISI) rather than at the two composite scores alone surfaces patterns the totals hide.

**Universal, not university-specific.** Two dimensions show the exact same score at every one of the five universities, which is unusual enough to flag as a pilot-level finding rather than noise:

- `permitted_encouraged_use` (PISI) scores 2 (emphasized) for all five. Every policy in this pilot affirmatively permits or encourages some use of AI — none of the five documents is a blanket restriction. This matters for how the REI scores above should be read: even Aarhus and Reykjavik, the two highest-REI universities, are not prohibiting AI use; they are regulating how it may be used.
- `equity_accessibility_inclusion` (PISI) scores 0 (absent) for all five. None of the five documents substantively addresses equity or accessibility in relation to AI use — for example, unequal access to paid AI tools, or accessibility for students with disabilities. This is the clearest gap the pilot surfaces: it is consistently absent rather than merely underdeveloped.

**Driven by document type, not country.** Two dimensions split cleanly along document type rather than nation or REI/PISI totals:

- `teaching_integration` (PISI) is highest for Aalto and Reykjavik — the two universities whose documents are "teaching and learning guidance" — and scores 0 for Aarhus and Oslo, whose documents are student- or examination-focused.
- `assessment_examination_control` (REI) is highest for Aarhus and Reykjavik, the two universities whose document type includes examination regulation specifically.

Taken together, these patterns suggest that what a policy emphasizes tracks the kind of document it is (teaching guidance vs. examination regulation vs. institution-wide policy) at least as strongly as it tracks which university or country produced it — a pattern worth testing explicitly if this pilot is extended to more institutions and more document types per institution.

## Methodology validation

**Data quality.** All 5 targeted documents were collected successfully: 0 failures, 0 duplicates, 29 chunks extracted. Every document passed the language check (English, confidence 1.00) and there were no missing-data warnings. All five were collected through the live HTTP pipeline (no Selenium fallback was needed for this pilot).

**Automated scores are a candidate-finder, not a second opinion.** The automated REI/PISI "hint" scores are produced by a keyword-matching rule (`modeling/indicators.py`), documented from the start as a narrower, more conservative signal meant to surface candidate evidence for human review — never a scoring verdict in its own right. Comparing them against your completed human coding confirms exactly that limitation rather than a code error: the automated score under-detects wherever a document expresses a dimension in paraphrase rather than in one of the literal configured keyword phrases, which is most of the real policy text. The gap is largest for PISI — Aalto (13.6 automated vs. 54.5 human) and Lund (9.1 automated vs. 54.5 human) — because pedagogical-support language is especially varied in wording across institutions. A secondary contributor is the scoring rule itself, which maps 0 matches → 0, 1 match → 1, 2+ matches → 2; a single strongly-worded sentence can therefore cap out at 1 even when a human coder would reasonably score it 2. One coincidental false positive was also found and is worth knowing about: Lund's automated `human_oversight_responsibility` score matched the generic phrase "responsible for" in the document's cover-page metadata ("Organisational unit responsible for the document..."), not in any substantive policy text — the automated score happened to land on the right number for the wrong reason. This was left as-is rather than "fixed," since narrowing that keyword hint is a research-design decision about `config/coding_dimensions.yaml`, not a code bug.

**A confirmed code bug was found and fixed.** `save_dimension_score()` and `save_index_result()` in `database.py` previously performed plain SQL inserts, so re-running the scoring pipeline — an ordinary, expected part of the workflow — silently duplicated every automated row rather than replacing it. This was the exact cause of the Policy Matrix page showing each set of automated component scores twice: the dashboard's own display logic was correct, it was faithfully rendering duplicated underlying rows. Both functions now delete any existing row with the same identity (document, dimension or index, coder, coding round) immediately before inserting the new one, so re-running the pipeline is now safe to repeat. Eight new tests (`tests/test_database.py`) lock in this behavior, including that different coders and different coding rounds correctly still get their own separate rows. Your live database was backed up, then deduplicated using only the confirmed-duplicate rows; your human annotations and human index results were left untouched and verified byte-identical before and after.

## Exploratory themes (BERTopic)

This section is explicitly exploratory. It was fit on 5 documents and 29 chunks — far too few for stable or generalizable topics — and BERTopic's topic assignments are computed entirely separately from the REI/PISI scores above; they are never used as evidence for them.

The real run (using the configured `all-MiniLM-L6-v2` sentence-transformer embeddings, not the earlier TF-IDF pipeline smoke test) found 2 topics with 0 outlier chunks across all 29 chunks:

| Topic | Chunks | Automatic keywords | Provisional manual label |
| --- | --- | --- | --- |
| 0 | 24 | generative ai, students, teachers, learning, tools, teaching, lund, student, responsible, assessment | "Responsible and safe AI use" |
| 1 | 5 | gai, use gai, allowed use, youre, gai exam, exam project, using gai, gai allowed | "Institutional support and AI literacy" |

Both manual labels are provisional researcher interpretations proposed from the automatic keywords — they have not been confirmed, and the dashboard's Topic Explorer page keeps them structurally separate from BERTopic's own output so one is never mistaken for the other.

**Institution-dominance caveat.** Topic 1 is flagged as institution-specific: 100% of its 5 chunks come from Aarhus University alone (entropy 0.0), so it more likely reflects Aarhus's particular document (which is structured around a "you're allowed / you're not allowed" GAI declaration format) than a theme shared across institutions. Topic 0 is not flagged — its 24 chunks are spread across all 4 other universities (Aalto, Lund, Reykjavik, Oslo), with Lund contributing the largest single share at 37.5%, well under the 70% dominance threshold. Document-type diagnostics reinforce the same caveat: Topic 1's chunks are 100% "student and examination guidance" documents, while Topic 0 draws from all four document types represented in the pilot. In short, Topic 0 is the closer of the two to a genuine cross-institution theme; Topic 1 should be read as "how Aarhus structures its GAI declaration requirement" rather than as a theme found more broadly.

## Limitations and next steps

**Sample size and scope.** Five universities, one per Nordic country, one document per university. This pilot demonstrates that the pipeline and coding scheme work end to end and surfaces patterns worth testing further — it is not a representative sample of Nordic (or even national) higher-education AI policy, and none of the findings above should be generalized beyond this specific set of five documents.

**Document type is a confound, not yet a controlled variable.** Because each university contributed exactly one document, and those documents differ in type (institution-wide policy, student guidance, examination guidance, teaching-and-learning guidance), the patterns in this report cannot cleanly separate "what this university emphasizes" from "what this kind of document typically covers." The `teaching_integration` and `assessment_examination_control` patterns above are the clearest examples — both track document type more tightly than they track country. Scaling this project up should either collect multiple document types per institution or explicitly stratify comparisons by document type.

**Automated scoring is a screening aid, not a validation of the human coding.** As detailed above, the keyword-matching rule under-detects paraphrased language by design and is not evidence against the human scores where they diverge — it is evidence of the rule's own narrowness. It remains useful for flagging candidate passages for review, not for auditing completed human coding.

**BERTopic results are a pipeline smoke test, not a finalized thematic analysis.** With only 29 chunks, 2 topics is close to the practical floor for meaningful clustering, and one of the two topics is already flagged as institution-specific rather than cross-institutional. Both manual topic labels remain provisional.

**Suggested next steps.** Expand the corpus (more universities, more document types per institution, and ideally a second country per Nordic country's language group) before drawing conclusions intended for publication; consider a second human coder and a round-2 recoding pass to enable the `validated_rei`/`validated_pisi` indices already supported by the schema but not yet populated; and revisit the `equity_accessibility_inclusion` keyword hints specifically, since its dimension score was 0 for every university in this pilot and it is worth confirming that is a genuine gap in these policies rather than an artifact of the coding scheme.
