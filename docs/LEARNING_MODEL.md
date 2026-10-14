# Milestone 3 assessment and learner contract

## What is verified

The generator uses the existing FTS5 context retrieval and immutable `Evidence`
objects. It considers at most 12 passages / 12,000 source characters. All
non-stopword topic tokens must appear together in a candidate sentence under the
existing SQLite tokenizer. This is a lexical relevance gate, not topic understanding.
Each question carries a topic/course via its session, source chunk ID, source
sentence and answer offsets, exact excerpt, format, level, key and deterministic ID.
Page/slide, filename and labels are always resolved from the source ledger.

The supported transformation is a cloze: remove a deterministic source span and
ask which text/value restores the original statement. The answer key is derived
from that span, never accepted from a model. Before issue, grading and source
review, `verify_question` re-resolves the chunk using the existing provenance
checks, rebuilds the entire question, and compares all fields. An invented key,
altered prompt, quote, option, identity or offset is rejected.

This verifies correspondence with the source. It cannot establish that the source
itself is factually correct, that its worked arithmetic is correct, or that recalling
the text demonstrates conceptual understanding. Conflicting documents can each
support a source-specific recall question; this is not a contradiction adjudicator.

## Formats and grading

- **MCQ:** one missing text span or stated number, with distinct alternatives.
  Numeric distractors are small deterministic offsets, not invented source claims.
  Exactly one option restores the source wording. A selected valid option is
  objectively marked correct/incorrect. An unknown option is rejected.
- **Short answer:** exact missing text, allowing Unicode normalization, casing
  and whitespace differences. Nonmatching wording is `needs_review`, score NULL;
  it may be a valid paraphrase. There is no subjective auto-grading, automatic
  semantic penalty, or teacher adjudication UI in this milestone.
- **Numerical:** the final supported literal number in the statement is hidden.
  Finite Decimal equality accepts equivalent notation (e.g. 9 and 9.0); no floating
  tolerance or unit conversion is silently applied. The prompt retains units and
  requests a number only. Invalid input prevents submission, allowing correction.
  These are numerical **value recall**, not new arithmetic problems. Scientific
  notation and grouping separators in source values are not parsed as full values;
  numeric spans longer than 18 characters are excluded.

The source must contain a usable statement of 25–450 characters and at least four
words. Sentence segmentation is heuristic, principally suited to English prose.
The system abstains from generating unsupported formats; it can return fewer than
the requested 1–8 questions. It never fills gaps with fabricated questions.

## Persistent learner state

`tutortrace.learning.sqlite3` is a separate local database. Its version-1 schema
contains `learners`, `topics`, `questions`, `sessions`, `session_questions`,
`attempts`, and `mastery`. Startup is transactional and idempotent; unknown
nonempty unversioned files and future versions are rejected, never overwritten.
There is no change to the established source database schema 2.

Topic identity hashes sorted normalized topic tokens plus sorted document IDs.
Different document selections have separate estimates, even for the same topic
label. An empty course selection is resolved to the current documents at issue
time. Adding documents can therefore create a new course identity on a later quiz.
Renaming an identical upload does not change its document identity.

Profiles use UUIDs and display names. All session, history, submission and abandon
queries enforce learner ownership. This separates records, **not access control**:
anyone using this local app can select another profile. No authentication is claimed.

## Mastery estimate and diagnostic

For each learner/topic/course, let C be objectively correct answers and I be
objectively incorrect answers. We use a Beta(1,1) prior and unit-weight counts:

`estimate = (1 + C) / (2 + C + I)`

The initial 0.5 is **unknown**, not measured 50% mastery. First practice with no
objectively graded history is marked diagnostic. New profiles start by selecting a
topic/course and completing that diagnostic. A short-answer-only submission that
needs review does not complete objective diagnosis; subsequent practice remains
diagnostic until an objective response is graded.

Correct adds one to C; incorrect adds one to I; needs-review increments a separate
review count and leaves the estimate unchanged. Each attempt records the before
and after estimates, learner response, score, feedback, UTC time and review signal.
No weighting by chosen difficulty, guessing correction, forgetting, prerequisite
inference or fitted parameters is used. This is **not BKT**, not a calibrated
probability of knowledge, and not a validated measurement of learning gains.

Adaptive choice:

| Observed state | Next practice level |
|---|---|
| No objective answers | easy (diagnostic) |
| Estimate < 0.45 | easy |
| Estimate >= 0.75 and at least 3 objective answers | hard |
| Otherwise | medium |

Manual level selection overrides the rule. Levels change scaffolding: MCQs offer
3/4/5 options, text blanks span 1/2/3 ending words, and numerical questions have
range+decimal-place hints / decimal-place hints / no hint. These differences are
not empirically calibrated difficulty bands.

## Repetition, caching and transactions

Fact IDs include document identity, physical location and normalized source
sentence. Formats, levels and overlapping chunks do not create new facts for an
unchanged statement. Facts in the learner's **last two issued sessions** are
excluded, including abandoned sessions. Within-quiz facts are unique. Other unseen
facts are preferred, then least-exposed eligible facts. Duplicated material in
different source documents can still be conceptually repetitive. This is a bounded
cooldown, not a validated spaced-repetition model.

Verified question payloads are persisted for reuse and review. IDs include the
generator version, chunk ID, sentence bounds, type and level. Cache rows are
compared with freshly rebuilt questions; caching never bypasses provenance.
Changing the generator algorithm requires a version change and may retire old
questions. Re-indexing sources retires old chunk IDs: unfinished stale quizzes
must be abandoned, historical grades remain, and unavailable citations are marked
instead of silently rebound. The current generator does not provide old-algorithm
reconstruction or a source-evidence archive beyond the existing source ledger.

`BEGIN IMMEDIATE` serializes issuing and submitting assessments. A partial unique
index permits only one open quiz per learner. Submission checks ownership,
question identity, source integrity and all responses before writing attempts,
mastery and completion in one transaction. A second submission is rejected; it
does not count twice. An injected storage failure rolls everything back. The source
and learner stores are separate files, so there is no cross-database commit lock;
concurrent source re-indexing after verification can retire a citation. Later review
detects that retirement rather than changing the recorded grade.

## Revision and learner-aware tutoring

Tracked topics are ordered by ascending estimate, then objective sample count and
stable label/ID. The top three receive a reason containing the estimate and actual
denominator, current source excerpts and canonical citations. Even a strong learner
can have a relative revision priority; the ordering is not a diagnosis of weakness.
Only exact source statements with explicit `requires understanding`, `prerequisite
is`, or `prerequisites are` language produce prerequisite suggestions. Otherwise
the app says the relationship is unknown.

The revision button prepares the topic, adaptive practice level and document scope
in the existing AI Tutor. The student explicitly starts inference. The existing
retrieval, provider errors, abstention, citation/quote checks and model limitations
are preserved. Citation validity does not prove model statements are entailed or
that the explanation is pedagogically appropriate for the learner.

Review signals (`source_recall_mismatch`, `numeric_recall_mismatch`,
`unverified_wording`) identify observable response problems. They do not establish
the underlying cognitive misconception. No clinical/educational diagnosis is made.
