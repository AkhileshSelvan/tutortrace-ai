# TutorTrace AI — final evaluation and release verification

Date: **14 October 2026, IST**. Tested application commit:
`36befa7d933d1cd7b6c74cee22ee1be1c1d15d31`. This release adds documentation and
a synthetic real-inference record only; no runtime code or test changes.
Windows, Python 3.11.17, approximately 16 GB RAM, CPU Ollama Qwen3 4B.

## Fresh release checks

All commands ran from the repository with `.venv\Scripts\python.exe` (abbreviated
as `python` below). These were executed, not inferred from earlier reports.

| Command/check | Actual outcome |
|---|---|
| `python -m pytest -q` | **216 passed in 88.82s**, zero failures or skips |
| `python -m scripts.smoke_test` | PASS: 2 originals, 2 duplicates, all 4 exact page/slide locations, reopened persistence, no-match search |
| `python -m scripts.learning_smoke --output data/release-learning-smoke.json` | PASS in 2.034s: all 3 formats, incorrect/correct/correct grades, 60% estimate, medium next level, cited revision, PDF rendering, fresh-process persistence |
| `python -m pip check` | No broken requirements found |
| `python -m scripts.learning_smoke --real-model --output docs/evaluation/release-real-smoke.json` | PASS: real answer, 3 claims / 3 validated support references; 70.544s inference, 72.383s full workflow |
| Fresh `python -m streamlit run app.py --server.headless true --server.address 127.0.0.1 --server.port 8502` | Started using isolated `data/release-startup`; `/_stcore/health` returned HTTP 200, `ok` |
| Anonymous GitHub repository API request | HTTP success; `private: false` for `AkhileshSelvan/tutortrace-ai` |

The 216 tests include the original 168 and 48 assessment/learner regressions.
Provider unit tests use deterministic mocks. Streamlit AppTest exercises actual
widgets, upload ingestion, quiz submission, review, revision handoff and a new app
session. An HTTP health check alone is not claimed as a complete browser demo.
The earlier actual browser demonstration and screenshot are retained in
[M3 verification](MILESTONE_3_VERIFICATION.md).

The release smoke creates a new synthetic learner and ingests the committed sample
PDF and PPTX. Its mixed diagnostic records 1 incorrect and 2 correct answers:
0.5 → 1/3 → 0.5 → 0.6. A separate Python process reopens both databases and
confirms the same dashboard, three attempts and two documents. This is real
persistence verification, not an in-memory restart simulation.

## Real inference, separate from unit tests

[Fresh release record](evaluation/release-real-smoke.json) contains the actual
question, selected source objects, accepted claims, quotes, timings and config.
Provider: local Ollama; model: `qwen3:4b`, installed digest
`359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`.
One bounded call: timeout 120s, context 2,048 tokens, output 500 tokens,
keyword retrieval, 2 passages / 1,800 source characters, temperature 0, seed 17,
thinking disabled. No model downloads or paid APIs were used.

It answered an energy revision request with conservation, kinetic-energy formula,
and the 2 kg / 3 m/s / 9 J example. All three returned support references passed
the existing source-ID and exact-quote checks. This is **one successful integration
case**, not a general model-quality or pedagogical-quality score. The earlier M3
call took 85.761s; the fresh release call took 70.544s. Neither is a latency guarantee.

## Earlier labelled tutoring evaluation (retained, not rerun in release)

The self-authored 13-case M2 set includes factual, paraphrased, multi-evidence,
unsupported, conflicting and similarly worded source questions, plus two injected
citation challenges. It was used during development and has no held-out split.

| Measurement | Recorded result | Interpretation |
|---|---|---|
| Keyword questions recovering all labelled sources | 11/11 source-labelled cases | Two unsupported cases excluded from this denominator |
| Labelled source-unit recall | 14/14 | Small controlled source set |
| Keyword selected-source precision | 14/21 | Seven retrieved units were outside expected labels |
| Hybrid selected-source precision | 14/26 | Worse precision on this set; optional embeddings are not a universal improvement |
| Real-model inference completed | 12/13 questions | One empty-retrieval question abstained before inference; zero errors |
| Expected response status | 13/13 | Status classification, not semantic answer accuracy |
| Accepted citation validity | 14/14 references | Provenance and quote validity, not entailment |
| Unsupported-question abstention | 2/2 cases | Includes pre-inference empty retrieval |
| Injected invalid citations rejected | 2/2 challenges | Deterministic validation checks, not model answers |
| Real evaluation latency | median 23.079s; max 103.197s | Includes retrieval/model loading; hardware-dependent |

Records: [keyword](evaluation/m2-keyword-retrieval.json),
[hybrid](evaluation/m2-hybrid-retrieval.json),
[real final run](evaluation/m2-real-final.json), and
[earlier run and defects](MILESTONE_2_VERIFICATION.md).
Term-matching checks are not semantic grading. No independent accuracy benchmark,
general injection-resistance guarantee, or live remote-provider evaluation is claimed.

## Simulated learners (retained M3 results)

[Input configuration](../evaluation/learning_profiles.json) prescribes responses;
[full output](evaluation/m3-simulation.json) retains every question, key, response,
source, score and level. Three profiles each complete nine three-question sessions.

| Profile | Completed sessions / answers | Final kinetic / power / potential estimates | Repeated facts | Top-priority changes |
|---|---|---|---|---|
| Beginner | 9/9; 27/27 | .364 / .455 / .636 | 0/27 | 0/8 transitions |
| Intermediate | 9/9; 27/27 | .545 / .727 / .727 | 0/27 | 3/8 transitions |
| Advanced | 9/9; 27/27 | .909 / .909 / .818 | 0/27 | 1/8 transitions |

Totals: **27/27 sessions, 81/81 answers, 0/81 repeated facts**, 3/3 restart
checks. Beginner: eight easy sessions, one medium; intermediate: easy/medium;
advanced: five hard sessions. Changes in top recommendation can include adding
newly tracked topics, not solely improvements in existing topics. These are
prescribed synthetic outcomes demonstrating software adaptation, **not actual
student learning gains** or calibrated mastery. Recall estimate is
`(1 + correct) / (2 + correct + incorrect)`; initial .5 means unknown.

## Reproduction and release boundaries

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m scripts.smoke_test
.\.venv\Scripts\python.exe -m scripts.learning_smoke --output data\learning-smoke.json
.\.venv\Scripts\python.exe -m scripts.evaluate_learning --output data\learning-evaluation.json
# Optional real local inference; requires installed/running Ollama:
.\.venv\Scripts\python.exe -m scripts.learning_smoke --real-model --output data\real-smoke.json
```

Source/learner databases, model files, credentials, environments and private
uploads are excluded from Git. The committed materials and inference records
contain self-authored synthetic content. Common credential-pattern and tracked
artifact checks are release hygiene, not a comprehensive security audit. The release
scan found no common credential patterns across 79 tracked/proposed files, no
tracked database/private-key artifacts, and no broken local links in the six
release documentation files. Explicit ignore checks confirmed databases, `.env`
and Streamlit secrets are excluded.

No submission-blocking runtime defect was found. No new features or refactors
were introduced. Fresh installation into a second environment was not performed
inside the timebox; the pinned prepared environment passed dependency checks.
No video was recorded or fabricated. No Devpost submission, deployment,
independent Claude Code audit, license-compliance certification, or hackathon
eligibility certification is claimed. The code still has no repository-wide
license; see [notices](THIRD_PARTY_NOTICES.md).
