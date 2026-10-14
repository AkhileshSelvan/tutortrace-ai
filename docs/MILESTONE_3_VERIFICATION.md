# Milestone 3 verification and review handoff

Date: 14 October 2026 (IST). Base: `52fa0ad92a18c33d70ecd6c91f40e4794e49319b`.
Environment: Windows, repository virtual environment, Python 3.11.17.
No new dependencies, model downloads, deployment or Devpost changes.

## Delivered behavior

- Source-derived MCQ, exact-wording short-answer and numerical value-recall quizzes.
- Topic/course and level selection; first objective practice is diagnostic.
- Full source transformation/key validation, canonical PDF/page-label/PPTX citations.
- One unfinished quiz per learner, fact-level cooldown, unseen-question preference,
  verified persistent question bank, explicit insufficient-material handling.
- Local profiles, atomic attempts/grades/mastery updates, before/after estimates,
  review signals, history, earlier answer review and progress chart.
- Source-backed revision priorities, explicit-source prerequisite statements, and
  learner-aware prompt/document handoff to the unchanged AI tutoring pipeline.

The assessment generator is deterministic, **not an LLM pretending to generate
verified keys**. These are recall exercises, not general semantic examinations.
Numerical questions recall source values, not new calculation problems. See
[LEARNING_MODEL.md](LEARNING_MODEL.md) for the complete contract and limitations.

## Executed commands and outcomes

All commands below ran from `D:\tutortrace-ai` using `.venv\Scripts\python.exe`.
Temporary data and detailed terminal logs are under ignored `data/`.

| Command | Observed result |
|---|---|
| `python -m pytest tests/test_learning.py tests/test_app.py tests/test_tutor_app.py -q` | 39 passed, 24.64 s (early implementation) |
| `python -m pytest tests/test_learning_app.py -q` | 2 passed, 16.25 s (live Streamlit harness workflow) |
| `python -m pytest -q` | Early full run: 203 passed, 91.06 s |
| `python -m pytest tests/test_learning.py tests/test_learning_app.py -q` | Expanded targeted run: 44 passed, 60.85 s |
| `python -m pytest -q` | **Final suite: 216 passed, 112.67 s; zero failures or skips** |
| `python -m scripts.evaluate_learning` | 27/27 sessions, 81/81 questions completed; final recorded run 6.633 s |
| `python -m scripts.learning_smoke` | Passed complete workflow and fresh-process restart; final recorded run 2.422 s |
| `python -m scripts.learning_smoke --real-model --output docs/evaluation/m3-real-revision.json` | Actual Qwen3 4B revision answered; 85.761 s inference, 88.899 s complete smoke |
| `python -m streamlit run app.py --server.headless true --server.address 127.0.0.1 --server.port 8501` | Server started; loopback health returned HTTP 200; live browser exercised |

The final 216 tests include **all 168 existing tests plus 48 assessment/learner
regressions**. No existing test files were changed. The initial labelled-PDF test
fixture omitted the mandatory initial page-label range; adding that range fixed
the fixture. It did not require changing the working PDF extractor.

Important regression coverage includes modified prompts/keys/options/quotes/IDs,
unsupported and malformed questions, PDF labels and slide locations, document and
learner isolation, fact cooldown across formats/levels, small-pool exhaustion,
exact Decimal grading, unsupported numeric notation, ungraded paraphrases,
diagnostic/adaptive mathematics, cache identity substitution, source corruption,
pipeline re-indexing, restart compatibility, incomplete/extra submissions,
concurrent duplicate submission, generation rollback, and failure injected after
attempt writes but before quiz completion. SQLite rolls attempts and mastery back.

## Database compatibility

The original source ledger remains schema **2** with the unchanged extraction
pipeline. Learner storage is a separate `*.learning.sqlite3` file at schema **1**.
Tests compare the complete source SQL dump before and after assessment use and
restart: no source changes occur. Existing migration and ingestion tests still pass.
Learner startup is transactional/idempotent and rejects unknown/future schemas.

A source pipeline-version bump alone preserves existing question evidence. An
actual source re-index retires old chunk IDs: stale questions fail verification,
historical grades remain, and newly issued questions use current evidence. The
application never silently reassigns an old question to a different source.

## Actual end-to-end demonstration

The smoke script ingested the repository's original sample PDF and PPTX, created
a learner, issued a diagnostic with all three formats, submitted one wrong MCQ
and two correct answers, and recorded:

- Source references: `energy_slides.pptx`, slide 1; `energy_notes.pdf`, page 1.
- Estimate sequence: 0.5 → 1/3 → 0.5 → 0.6. Next level: medium.
- A source-backed revision reason with the actual denominator of 3.
- Successful rendering of the cited PDF page as PNG.
- A **separate Python process** reopening both databases and recovering the same
  dashboard, all 3 attempts, and both documents.

The live in-app browser separately loaded the sample course, created a demo
learner, generated a mixed diagnostic, selected `between` for the conservation
MCQ, entered `forms` and `9`, and displayed incorrect/correct/correct with a 60%
estimate and page/slide answer review. The Streamlit harness also exercises real
file upload, input validation, learner switching, revision handoff and app-session
restart. Only self-authored demo data was used. Browser checks exposed the need
to open the sidebar in the narrow in-app viewport before using its controls.

Machine-readable records:

- [Deterministic smoke](evaluation/m3-smoke.json)
- [Real revision request, claims and supporting evidence](evaluation/m3-real-revision.json)
- [Simulation configuration](../evaluation/learning_profiles.json)
- [Simulation inputs and every observed response/outcome](evaluation/m3-simulation.json)
- [Live dashboard screenshot](evaluation/m3-dashboard.jpg)

The final build was exercised again in the browser after the interrupted work
session resumed. It displayed 2 matched / 1 not matched, a 60% estimate, medium
next difficulty, the scoped revision prompt, and chart points at 1/3, 0.5 and 0.6.
A final attempt to stop/restart that live server was rejected by automatic approval
review with only `blocked by policy` supplied. It was left running. The executed
fresh-Python-process smoke and independent Streamlit app-session restart tests
remain the persistence evidence; no blocked command is counted as a successful restart.

## Real inference

Installed `qwen3:4b`, digest
`359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`,
was called through the existing Ollama adapter. One bounded request used a
120-second timeout, 2,048 context tokens, 500 output tokens, and two retrieved
passages / 1,800 source characters. Thinking remained disabled by the adapter.
The model returned three statements and three validated supporting citations:
energy conservation, the kinetic-energy formula, and the 2 kg / 3 m/s / 9 J example.
Citation validation establishes source provenance and exact quoted support;
it is not a general semantic-accuracy score or proof of pedagogical quality.

The host had 15.64 GiB physical RAM and 1.36 GiB available at the pre-check.
No unrelated application or development process was stopped. No extra model was
downloaded. Quiz generation/grading made zero model calls. The local service and
test app were started when absent; the isolated test app was restarted for checks.

## Scripted personalization evaluation

Three original source sets (PDF/PPTX) contain 12 examples per topic. Each scripted
learner takes three rounds over kinetic energy, power and potential energy, three
questions per session. Input bit patterns explicitly prescribe right/wrong answers.
The report retains every question, key, response, citation, level and result.

| Profile | Sessions / answers completed | Final kinetic / power / potential estimates | Repeated facts | Top-priority changes |
|---|---|---|---|---|
| Beginner | 9/9; 27/27 | 0.364 / 0.455 / 0.636 | 0/27 | 0/8 transitions |
| Intermediate | 9/9; 27/27 | 0.545 / 0.727 / 0.727 | 0/27 | 3/8 transitions |
| Advanced | 9/9; 27/27 | 0.909 / 0.909 / 0.818 | 0/27 | 1/8 transitions |

No fact repeated either within the two-session cooldown or anywhere in each
recorded profile's run. Restart checks passed for 3/3 profiles. Beginner practice
was easy for eight sessions and medium for the last; intermediate levels moved
between easy and medium; advanced practice reached hard in five sessions.
Recommendation transitions can include the addition of newly tracked topics,
so they are not all attributable to improvement in an already tracked topic.

**These are prescribed simulated outcomes, not demonstrated real-student learning
gains, calibrated mastery probabilities or independently assessed model quality.**

## Review and next milestone

`git diff --cached --check` passed. Staged text/JSON was checked for common API
key/token/private-key patterns with no findings. Tracked-file inspection found no
local database or private-key files; `git check-ignore` confirmed source/learner
databases, `.env` and Streamlit secrets are excluded. The screenshot contains only
self-authored sample material and a synthetic demo profile. `origin/main` was
fetched and matched the base commit before the milestone commit, allowing a
normal fast-forward push without rewriting history.

Review `assessment.py`, `learning.py`, `learning_ui.py`, the two new test modules,
evaluation/smoke scripts and their records. Existing source/tutor behavior is
preserved; `app.py` adds the practice panel and `tutor_ui.py` adds a stable scope
widget key for the revision handoff. No credentials, private uploads or local
databases belong in the commit. Independent Claude Code review has not occurred.

Ready for a bounded Milestone 4 after independent review, with the scope explicitly
limited to reliable recall practice. Deeper conceptual question generation,
verified arithmetic problems, teacher-reviewed subjective grading and validated
learning outcomes remain future work. Do not present video, OCR, diagram
understanding or calibrated personalization as implemented.
