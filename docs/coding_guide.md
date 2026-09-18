# Coding Guide: Nordic University AI Policy Tracker

This guide is what a human coder (currently: Patricia, as the pilot's sole
coder) uses to assign a 0-2 ordinal score to each dimension for each
document. It is also what a second coder would use, later, to make
inter-coder comparison meaningful.

## The scale (applies to every dimension)

| Score | Label | Meaning |
|---|---|---|
| 0 | Absent | The document does not substantively address this dimension. A stray, incidental word does not count. |
| 1 | Mentioned | The dimension appears, but briefly, generally, or without concrete instructions, examples, or procedures. |
| 2 | Emphasized | The dimension is discussed clearly, repeatedly, or through concrete requirements, procedures, examples, or named resources. |

**Every score of 1 or 2 must be linked to at least one evidence passage** —
a verbatim quotation from the document, stored with its character offsets
into `cleaned_text`. A score of 0 does not require an evidence passage
(there's nothing to quote for an absence), but the coder may still note
*why* they concluded it was absent if that's non-obvious (e.g. "document
discusses disclosure generally but never for this specific audience").

## The core interpretive rule: read for stance, not for keywords

A dimension's keywords (config/coding_dimensions.yaml) exist only to help
you *find* candidate sentences. They do not determine the score. Read every
candidate sentence and ask: **what is this sentence actually claiming or
requiring?**

### Worked negation example (from the project brief)

> "AI detectors are unreliable and should not be used as the sole basis for
> disciplinary action."

This sentence contains "AI detector" and "disciplinary action" — the exact
keywords for the `ai_detection_surveillance` dimension. But the sentence
**criticizes** detection tools and **prohibits** relying on them. It is not
evidence that the institution deploys or endorses surveillance. Scored
correctly, this sentence contributes **0** (or, if the document elsewhere
substantively discusses the *unreliability of detection* as a reason for a
more human-centered process, it might support a different dimension, like
`human_oversight_responsibility`, if it's framed that way).

### Other stance patterns to watch for

- **Prohibition of the dimension's own subject** ("must not be used") is
  the clearest negation case, but also watch for:
- **Hedged/hypothetical framing** ("in some cases", "for example",
  "hypothetically") — often signals the sentence is illustrating a general
  principle, not stating an institutional rule. Read the surrounding
  paragraph before scoring.
- **Quoted or reported language** — a policy summarizing someone else's
  view ("some critics argue that AI detection is necessary") is not the
  institution's own position.
- **Exceptions** ("AI is allowed except during proctored exams") — score
  the *actual* rule, including its scope, not just the first clause.
- **Recommendations vs. obligations** — "should" language is generally
  weaker evidence than "must"/"required to", and this difference matters
  for distinguishing a 1 from a 2, not just for polarity.

## Restriction and Enforcement Index (REI) dimensions

### 1. Prohibition or restriction (`prohibition_restriction`)

**Definition:** The document states that certain generative AI uses are
not allowed, or restricts use to certain conditions.

**Inclusion:** Explicit "not allowed", "prohibited", "may not", scoped
restrictions ("not allowed unless the syllabus says otherwise").

**Exclusion:** A description of what IS allowed, without a corresponding
prohibition, is not evidence for this dimension (that belongs under
`permitted_encouraged_use`). A hedge about detection tools' unreliability
is not a restriction on AI use itself.

**Score 0 example:** Document never states any AI use is disallowed.

**Score 1 example:** "Using AI for some tasks may not be appropriate."
(vague, no concrete scope).

**Score 2 example (Aarhus, pilot):** "You're not allowed to use GAI to do
your exam project for you." (concrete, scoped, unambiguous).

**Ambiguous case:** "AI use is subject to course-specific rules." This
implies restriction exists somewhere but doesn't state it in *this*
document — score 1 (mentioned: acknowledges restriction is possible,
without concrete detail) rather than 0, since the document does
substantively flag that restrictions apply.

**Negation example:** "Prohibiting the use of AI ... is not generally
advisable" (Aalto, pilot) is an argument AGAINST prohibition, not evidence
of a prohibition — do not score this sentence toward this dimension.

---

### 2. Punishment or disciplinary consequences (`punishment_disciplinary`)

**Definition:** The document describes consequences imposed on a student
or staff member for policy violations.

**Inclusion:** "disciplinary proceedings", "sanctions", "expulsion",
"formal disciplinary process", references to a named misconduct process.

**Exclusion:** A general reference to "academic integrity rules apply" with
no description of consequences is `academic_misconduct_framing`, not this
dimension, unless it also names a consequence.

**Score 1 example:** "Consequences may follow." (vague).

**Score 2 example (Reykjavik University, pilot):** "Serious breaches shall
be referred to RU's formal disciplinary process."

**Ambiguous case:** "The same rules and sanctions apply as for other forms
of academic misconduct" (RU) — this references sanctions without detailing
them, but ties explicitly and directly to an existing formal process; treat
as score 2 given the explicit "formal disciplinary process" language
elsewhere in the same document, or score 1 if this were the *only* mention.

---

### 3. Academic misconduct framing (`academic_misconduct_framing`)

**Definition:** The document explicitly frames improper AI use as academic
dishonesty, cheating, or plagiarism.

**Inclusion:** "considered cheating", "academic misconduct", "plagiarism".

**Exclusion:** Disclosure or citation requirements alone (without framing
non-compliance as dishonesty) belong under `mandatory_disclosure` or
`transparency_citation`.

**Score 2 example (Aalto, pilot):** "Utilising AI in a learning task
contrary to the teacher's instructions will be considered cheating."

---

### 4. AI detection or surveillance (`ai_detection_surveillance`)

**Definition:** The document describes institutional use of, or reliance
on, tools to detect AI-generated content.

**Inclusion:** Naming detection software, describing a detection process
the institution actually uses or endorses.

**Exclusion (critical — see worked example above):** Sentences that
criticize, limit, or express skepticism about detection tools are NOT
evidence of endorsement. Read carefully for stance.

**Score 1 example (Reykjavik University, pilot):** "Tools such as Turnitin
may offer indications of AI-generated text, but no software can provide
definitive proof." — mentions detection tools, but the framing is
skeptical/limiting, not an endorsement of relying on them; the sentence
still substantively discusses the *existence and limits* of detection at
the institution, so it is not simply absent either. Score 1, not 2 or 0,
with an uncertainty_flag noting the mixed framing.

---

### 5. Mandatory disclosure of AI use (`mandatory_disclosure`)

**Definition:** The document requires users to state when/how/whether they
used AI.

**Score 2 example (Aarhus, pilot):** "You must submit a declaration that
contains: 1) confirmation you used GAI, 2) the name of the GAI
applications you used, and 3) an explanation of how you used the
applications."

**Ambiguous case:** "You may be asked to describe how AI was used" (Aalto)
— conditional on the teacher asking, not a blanket requirement. Score 1.

---

### 6. Assessment and examination control (`assessment_examination_control`)

**Definition:** The document sets rules specifically for exam or graded-
assessment contexts.

**Score 2 example (Reykjavik University, pilot):** "AI tools are generally
prohibited in final examinations, unless otherwise specified in the course
syllabus" plus detailed "secure vs. less secure" assessment guidance.

---

### 7. Privacy, security, or data-protection restrictions (`privacy_security_restriction`)

**Definition:** The document restricts what may be entered into AI tools
for privacy/security/legal reasons.

**Score 2 example (Aarhus, pilot):** "Never upload confidential or
sensitive personal data to GAI applications." (GDPR reference).

**Note on dual-use with PISI:** this dimension captures the *restriction*
framing (what you must NOT do). The parallel PISI dimension
`privacy_awareness_safe_use` captures *supportive* framing (guidance on how
to use tools safely). The same paragraph can score on both if it both
restricts and educates — score each dimension on its own terms.

## Pedagogical Integration and Support Index (PISI) dimensions

### 8. Permitted or encouraged use (`permitted_encouraged_use`)

**Score 2 example (Aalto, pilot):** "The use of AI-based technologies is
allowed as a support for teaching and learning unless instructed
otherwise."

---

### 9. AI literacy (`ai_literacy`)

**Definition:** The document addresses building understanding of how AI
works, its capabilities and limits, as a competency to develop.

**Score 1 example (UiO, pilot):** "Make sure to familiarise yourself with
what AI is." (brief).

---

### 10. Critical evaluation of AI outputs (`critical_evaluation`)

**Score 2 example (Reykjavik University, pilot):** "AI tools generate
likely answers but cannot verify their own accuracy... users must verify
all information independently," combined with explicit critical-thinking
emphasis throughout the document.

---

### 11. Responsible use (`responsible_use`)

**Definition:** General framing of AI use as something to be done
responsibly/ethically (broader than any single other dimension).

**Score 1 example:** A single mention of "responsible use of AI" with no
further elaboration.

---

### 12. Teaching integration (`teaching_integration`)

**Definition:** Guidance on how teachers should incorporate AI into course
design, assignments, or learning objectives.

**Score 2 example (Aalto, pilot):** Multi-point guidance on how teachers
set course-specific restrictions tied to learning objectives.

---

### 13. Student support (`student_support`)

**Score 1 example (UiO, pilot):** Points to "reliable sources" generally.

**Score 0 example:** No named support resource or service for students at
all (Aarhus's pilot document, which is procedural/rule-focused, does not
name a student support resource for AI specifically).

---

### 14. Staff or teacher support (`staff_support`)

**Score 2 example (Reykjavik University, pilot):** Names a specific
resource: "the AI project manager within the Teaching Development Office."

---

### 15. Transparency and citation guidance (`transparency_citation`)

**Score 2 example (Aarhus, pilot):** "You must cite it in the same way you
cite quotations from other secondary sources."

---

### 16. Equity, accessibility, and inclusion (`equity_accessibility_inclusion`)

**Definition:** The document addresses fairness in access to AI tools
(e.g. cost, licensing) or accessibility/inclusion considerations.

**Score 1 example (Aalto, pilot):** "The teacher must ensure that students
are not put in an unequal position" / "cannot require the student to
purchase licenses" — addresses equity of access, but narrowly (licensing
only), so 1 rather than 2 unless elaborated further.

---

### 17. Privacy awareness and safe use (`privacy_awareness_safe_use`)

**Definition:** Supportive/educational guidance on using AI tools safely
(distinct from dimension 7's restriction framing — see the dual-use note
above).

**Score 1 example (UiO, pilot):** "Avoid sharing sensitive information and
copyrighted material in AI tools without approval." — framed as guidance/
advice to the student, not as an absolute institutional prohibition, so it
is coded here as well as potentially under `privacy_security_restriction`
depending on how absolute the language is; document both codings and use
uncertainty_flag if genuinely torn.

---

### 18. Human oversight and individual responsibility (`human_oversight_responsibility`)

**Score 2 example (Reykjavik University / Aalto, pilot):** "Students are
always responsible for their own work and must be able to explain or
defend it" / "The student is always responsible for the content of their
submitted work."

## Evidence requirements (all dimensions)

- Evidence passages are copied **verbatim** from `cleaned_text`.
- Store `evidence_start_offset` / `evidence_end_offset` as character
  positions into that document's `cleaned_text`, so any reader can jump
  straight to the passage.
- A score of 2 built on repetition (the dimension recurs several times)
  should cite the clearest single passage as the primary evidence, with a
  note in `uncertainty_note` pointing to the fact that it recurs, if that
  detail matters for interpretation.

## Uncertainty

Use `uncertainty_flag=True` whenever you are genuinely torn between two
adjacent scores, or between assigning a passage to this dimension vs. an
adjacent one (see the dual-use privacy note above). Write what you were
torn between in `uncertainty_note`. This is not a sign of a bad coding
decision — recording it is the point.

## Aggregation

Document-level scores aggregate to university-level scores as the mean
across that university's documents (with document count preserved). This
pilot has exactly one document per university, so university-level and
document-level scores are numerically identical for now — the aggregation
logic exists so it behaves correctly once a university has more than one
document.

## Missing-data treatment

A dimension that was not coded (rather than coded as 0) is left out of
`component_scores` entirely and reflected in the index's `confidence`
field (`n_dimensions_coded / n_dimensions_total`). See
`src/nordic_ai_policy_tracker/modeling/indices.py`. Never backfill a
missing score with 0.

## Validation process (pilot)

Single coder (Patricia). No inter-coder reliability is reported for the
pilot — see `docs/methodology.md` for why, and for the planned weighted
Cohen's kappa procedure once a second coder joins. An intra-coder check is
planned: recode all five pilot documents after a ~2-3 week interval and
compare round 1 vs round 2 using
`src/nordic_ai_policy_tracker/modeling/validation.py::compare_coding_rounds`.
Agreement is reported as a plain percentage (not chance-corrected) and is
explicitly NOT claimed to rule out individual coder bias — it only checks
whether the same coder applies the guide consistently to themselves over
time.

## Limitations of this guide

This guide was written by inspecting the five pilot documents' actual
content in order to source good/bad examples grounded in real text, which
is good practice but also means the examples skew toward what these five
documents happen to contain. As more documents are added (see
`docs/limitations.md`), examples for dimensions poorly represented in the
pilot (e.g. `equity_accessibility_inclusion`, which appears only thinly)
should be revisited and expanded.
