# Milestone 2 — real tutoring verification and review handoff

Completed verification on **14 October 2026 (IST)** in `D:\tutortrace-ai`.
Base: `50cc0adc700ce55af46acc75fd4b1aeb1fc6aa20`, branch `main`, initially clean
and synchronized with `origin/main`. The session was interrupted and resumed;
completed outputs were inspected before continuing. No Devpost changes, deployment,
model downloads, new dependencies or unrelated project changes were performed.

## Environment and resource decisions

- Python 3.11.17, SQLite 3.53.1, Streamlit 1.65.0, PyMuPDF 1.28.2,
  python-pptx 1.0.2, pytest 9.1.1; existing requirements retained.
- Approximately 15.64 GiB physical RAM; Intel UHD integrated graphics. Ollama
  selected CPU execution. Initial disk inspection found approximately 29.5 GiB
  free on D:. No additional model download was needed.
- Initial available RAM: **1,161,684 KiB (1.11 GiB)**. After resuming, one reading
  fell to **390,280 KiB (0.37 GiB)**. Later readings fluctuated up to
  **2,426,140 KiB (2.31 GiB)**; the final documented idle reading was
  **1,445,228 KiB (1.38 GiB)**. These are observed snapshots, not a measured causal
  improvement from terminating applications. The approximately 4 GB target was
  not safely achieved.
- Process inspection found no orphaned TutorTrace test processes to terminate.
  Other memory-heavy processes belonged to active/unrelated apps or development
  sessions and were left alone. No Windows/security services, browser windows,
  WSL/Docker workloads, Codex or unrelated applications were stopped.
- Ollama was initially stopped and was started on loopback. It was restarted after
  the interrupted session left it unavailable. Existing TutorTrace servers were
  not terminated during this milestone; when no healthy server remained, the app
  was started again on port 8501.
- Ollama was configured for one loaded model and one parallel request. Embedding
  requests use `keep_alive=0`; generation uses a short keep-alive. `/api/ps` confirmed
  an empty model inventory after unloading. The service remains available.
- Ollama version: **0.30.10**. Selected **qwen3:4b**, Q4_K_M, approximately 2.50 GB
  on disk, the smallest already-installed general-purpose generation model among
  the inspected base models. Gemma3 4B was approximately 3.34 GB and Qwen2.5 Coder
  7B approximately 4.68 GB. Existing cloud aliases were not used. No LocalPilot
  custom model or private-project code was reused.
- Qwen model digest observed in the inventory:
  `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`.
  The installed embedding model was **nomic-embed-text:latest**, approximately
  274 MB, digest `0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f`.
  Server logs reported a 576 MiB Qwen KV buffer at 4,096 context tokens and a
  260.86 MiB embedding model buffer; these are component allocations, not total
  process RAM requirements.

## Implemented behavior

The existing M1.1 ingestion, source ledger, schema migration, pipeline-version
compatibility, original preservation and standalone search remain in place.
The only source-store addition is a bounded, provenance-verified corpus reader
for optional semantic retrieval. The database stays at schema 2 and the extraction
pipeline version is unchanged.

New modules implement:

- A provider-neutral completion/status contract, real local Ollama inference and
  an explicitly credential-configured OpenAI-compatible remote adapter.
- Scoped question retrieval, reciprocal-rank fusion, overlapping-window
  deduplication, optional local embeddings and configurable passage/character limits.
- A separate disposable embedding cache keyed by model digest, chunk ID and text
  hash, with visible keyword fallback when semantic retrieval fails.
- Structured answer claims, exact supporting quotations, model abstention,
  conflict presentation and unsupported-aspect warnings.
- Request-local source aliases bound to immutable canonical Evidence objects.
  Every displayed reference must belong to that question's selected evidence;
  every quote must occur exactly in its excerpt. The cited chunk is resolved again
  through M1.1 provenance verification before display. The model does not construct
  citation filenames, physical pages, slides or original-file links.
- An explicit model abstention suppresses all accompanying claims and citations,
  with a visible explanation. This never converts a failed or abstained response
  into an answer. Malformed accepted-answer structures and invalid references
  still fail closed.
- A Streamlit AI Tutor panel with document/course selection, provider/model status,
  question input, accepted-answer/abstention/error states, source inspection,
  exact-page PDF preview and original PDF/PPTX downloads.

Inference defaults: local Qwen3 4B, temperature 0, seed 17, thinking disabled,
4,096 context tokens, 900 output tokens and 120-second socket timeout. Retrieval
defaults: five complete chunks, 3,600 source characters, optional semantic corpus
limit 500 and cosine threshold 0.35. No paid API or credentials were used.

## Executed commands and results

All Python commands below used `.venv\Scripts\python.exe` from the repository.

| Command/check | Actual outcome |
| --- | --- |
| `python -m pytest -q` before edits | 90 passed in 51.13s |
| Original suite after adding the tutor | 90 passed in 76.77s |
| Initial new provider/tutor tests | 62 passed, 2 setup/teardown errors: an oversized parametrized value exceeded Windows' environment-variable length limit in `PYTEST_CURRENT_TEST` |
| New tests after short parameter IDs and UI coverage | 66 passed in 125.15s |
| Complete suite before final provider-error hardening | 158 passed in 108.59s |
| Final `python -m pytest -q` | **168 passed in 273.69s; no failures or skips** |
| `python -m scripts.smoke_test` | PASS: two originals, two duplicate checks, four exact PDF/PPTX source locations, restart persistence and no-match search |
| `python -m pip check` | No broken requirements found |
| Bounded local Qwen probe, 2,048 context tokens / 30 output tokens | Actual JSON `{"answer":"ready"}` in **13.39s**, including model load; no OOM error |
| First actual tutor call | Kinetic-energy formula and example from `energy_notes.pdf, page 1`, with valid exact quotes, in **55.23s** |
| `python -m scripts.real_model_smoke --hybrid` | PASS: actual embedding + Qwen generation, canonical PDF citation, exact quotes, reopened store and no-model empty-retrieval abstention; answer pipeline **82.65s** |
| Streamlit startup | Started on `127.0.0.1:8501`; health **HTTP 200 / ok**, root **HTTP 200** |
| `git diff --check` | Passed; only Windows LF/CRLF conversion notices |

The final suite contains the original 90 cases plus 78 new cases. New coverage
includes invalid/foreign citation IDs, invented quotes, source isolation, changed
evidence during inference, unsupported questions, empty retrieval, missing models,
timeouts, malformed responses, error recovery, provider transport/authentication
failures, embedding cache persistence and invalidation, hybrid fallback, corpus
limits, source-database compatibility and Streamlit answer/error flows.
Final provider-error hardening also covers malformed remote completion envelopes,
invalid URL ports/hosts, invalid model capability metadata and interrupted HTTP
response bodies. These checks do not alter successful inference behavior.

Real model checks are explicit scripts, not silently skipped pytest cases.
The remote adapter was tested using deterministic contract doubles, not live API
credentials. Existing PDF/PPTX citations, corrupted-evidence checks, schema-1
migrations and process-interrupted re-index rollback remain covered by the original
suite. Citation validity is **not** represented as semantic correctness of every claim.

Startup command:

```powershell
.venv\Scripts\python.exe -m streamlit run app.py --server.headless true --server.address 127.0.0.1 --server.port 8501
```

## Reproducible evaluation

The self-authored [dataset](../evaluation/cases.json) contains six generated
PDF/PPTX documents and thirteen questions: factual, paraphrased, multi-passage,
unsupported, citation challenges, contradictory notes, ambiguous references and
similar terminology with different facts. See [metric definitions](../evaluation/README.md).

Executed:

```powershell
.venv\Scripts\python.exe -m scripts.evaluate_tutor --output data\m2-retrieval-evaluation.json
.venv\Scripts\python.exe -m scripts.evaluate_tutor --real --output data\m2-real-evaluation.json
.venv\Scripts\python.exe -m scripts.evaluate_tutor --real --only unsupported_overlap similar_terminology --output data\m2-diagnostic-evaluation.json
.venv\Scripts\python.exe -m scripts.evaluate_tutor --real --only unsupported_overlap similar_terminology forged_citation --output data\m2-contract-retest.json
.venv\Scripts\python.exe -m scripts.evaluate_tutor --real --output data\m2-final-evaluation.json
.venv\Scripts\python.exe -m scripts.evaluate_tutor --hybrid --output data\m2-hybrid-retrieval.json
```

The [initial real run](evaluation/m2-real-initial.json) produced three rejected
responses out of thirteen questions, all due to contradictory status/claim fields.
Diagnostic raw outputs showed a model choosing abstention while generating either
irrelevant facts or an otherwise supported answer. The response field order/prompt
was tightened, and explicit abstention was made conservative by withholding all
accompanying claims. The [final real run](evaluation/m2-real-final.json) records
all cases and raw completions, including the withheld content.

| Final keyword + Qwen diagnostic | Observed result |
| --- | --- |
| Questions run | 13 |
| Actual completed inference requests | 12; one empty-retrieval question did not call a model |
| Questions retrieving all labelled source units | 11 / 11 source-labelled questions |
| Labelled source-unit recall | 14 / 14 |
| Selected-source label precision | 14 / 21 |
| Displayed citations with valid request membership and exact quotes | 14 / 14 |
| Independently injected invalid-reference/quote challenges rejected | 2 / 2 |
| Unsupported questions abstained | 2 / 2; one retrieval abstention and one model abstention |
| Expected status checks | 13 / 13; ambiguous case permits several statuses |
| Inference/validation errors | 0 / 13 |
| End-to-end latency across all thirteen cases | Median 23.079s; maximum 103.197s |

For the twelve cases that actually called the model, median end-to-end latency was
26.0835s; maximum was 103.197s. This includes retrieval and model loading.

These are development-set diagnostics with explicit denominators, **not** a
faithfulness score, independent benchmark, calibrated confidence or learning-gain
measurement. Expected-term checks are simple string tests; they are not semantic
grading. The small set was used during implementation and has no held-out split.

[Hybrid retrieval](evaluation/m2-hybrid-retrieval.json) also recovered all labelled
sources (11/11 questions, 14/14 source units), but label precision was **14/26**,
worse than keyword-only **14/21**. Median retrieval time was 0.631s, maximum 1.486s
on this run. Semantic retrieval returned irrelevant passages even for the capital
question, so retrieval presence is never treated as answerability. Full hybrid
generation quality was not evaluated across all thirteen questions; one real
hybrid tutor integration was run. Semantic retrieval remains opt-in.

A separate real embedding probe asked “Which quantity represents how quickly a
job gets done?” Keyword retrieval found nothing. Hybrid retrieval returned the
relevant power slide at rank 2, behind an irrelevant kinetic-energy passage.
This demonstrates real semantic recall and also a remaining ranking weakness.

## Review findings and remaining limits

- Some real responses include unasked topics in `unsupported_aspects`; they remain
  visibly labelled as unsupported and are not accepted factual answer claims.
- A model can attach a valid quote to an incorrect claim. A dedicated regression
  documents this boundary; no automated semantic-entailment guarantee is claimed.
- Prompt injection is mitigated through system instructions, structured output and
  source/quote validation, but one successful adversarial fixture is not proof of
  general resistance.
- Local latency and memory availability vary substantially. No safe way to reclaim
  approximately 4 GB was found without disturbing unrelated work.
- No live remote-credential test, persistent chat, personalization, mastery,
  assessment, video, OCR or diagram understanding was implemented.
- Embedding cache size is bounded per retrieval scan, not automatically pruned over
  the lifetime of the library. Source character limits are not exact token limits.
- See [known limitations](KNOWN_LIMITATIONS.md) for the complete current list.

## Changed files and independent-review readiness

Runtime changes: `app.py`, `tutortrace/persistence.py`,
`tutortrace/providers/{llm,http,adapters}.py`, `tutortrace/retrieval/context.py`,
`tutortrace/tutoring.py`, `tutortrace/tutor_ui.py`.

Verification additions: `tests/test_providers.py`, `tests/test_tutoring.py`,
`tests/test_tutor_app.py`, `scripts/evaluate_tutor.py`, `scripts/real_model_smoke.py`,
`evaluation/{cases.json,README.md}`, and four public synthetic evaluation reports
under `docs/evaluation/`. Documentation/configuration: `.env.example`, `README.md`,
`docs/ARCHITECTURE.md`, `docs/KNOWN_LIMITATIONS.md`, `docs/AI_DISCLOSURE.md`, this file.

The diff and selected files were reviewed. A credential-pattern scan found no
private-key, AWS-key, GitHub-token or API-key candidates. Explicit ignore checks
confirmed `.env`, Streamlit secrets, original/embedding databases and the virtual
environment remain excluded. The committed reports contain only synthetic
evaluation material; credentials and local runtime logs are not included.

No source-ledger schema or extraction pipeline change is needed. Original M1.1
behavior remains regression-tested. Ready for independent review of source
isolation, abstention precedence, provider errors, cache boundaries and evaluation
claims. Milestone 3 can build on this interface after that review; no claim is made
that a hackathon-ready personalization or multimodal learning loop is complete.

Primary API references used during implementation:
[Ollama chat](https://docs.ollama.com/api/chat),
[structured outputs](https://docs.ollama.com/capabilities/structured-outputs), and
[embeddings](https://docs.ollama.com/api/embed).
