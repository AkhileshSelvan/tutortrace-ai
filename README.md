# TutorTrace AI

Track D — Personalized Tutoring & Adaptive Learning, Multimodal AI Hackathon 2026.

**Submission release — Milestones 1–3:** a PDF/PPTX evidence library, source-grounded AI tutor, and persistent adaptive recall practice. Upload educational materials,
search extracted text, inspect exact page/slide citations, preview PDF pages,
download the byte-identical original, and ask a configured model questions about
selected documents. Retrieval alone needs no model or API key. Local AI uses
Ollama; remote inference requires separately supplied API credentials.
Create a learner profile, complete a source-derived diagnostic quiz, review cited
answers, track topic estimates, and prepare personalized AI revision. Video
ingestion and visual understanding remain future milestones.

## The problem

Students need to connect an explanation or practice answer to the actual chapter
or slide they are studying. A fluent answer without inspectable evidence makes
mistakes difficult to spot, while an opaque progress score makes revision hard to
prioritize. TutorTrace connects original materials, cited explanations, verifiable
recall exercises and a transparent learner history in one local app.
It is a working prototype, not a demonstrated improvement in student learning.

## Implemented features and architecture

- Preserve original PDF/PPTX bytes, extract text by physical page/slide, detect
  duplicate uploads, and retain ingestion history and PDF-defined page labels.
- Search with SQLite FTS5; optionally combine local embedding ranks for paraphrases.
- Ask local Ollama or a configured remote model; validate request-specific source
  IDs and exact quotes, expose excerpts, and show abstention or inference errors.
- Generate source-cloze MCQs, exact-wording short answers and numerical value
  recall, with deterministic answer keys and recent-fact repetition prevention.
- Persist profiles, diagnostics, grades, recall estimates and revision priorities;
  pass the selected learner's topic/course and practice level into the AI tutor.

```text
PDF / PPTX -> extraction -> source SQLite + FTS5 -> verified evidence
                                                    |          |
                                           LLM tutor        cloze quiz
                                                    |          |
                                        citation checks     exact grading
                                                    |          |
                                               Streamlit <- learner SQLite
                                                               |
                                                    revision priorities
```

Inference is separate from retrieval and assessment. Source schema 2 and learner
schema 1 are independent; existing ingestion migrations remain unchanged.
See [final architecture](docs/FINAL_ARCHITECTURE.md),
[demo walkthrough](docs/DEMO_SCRIPT.md), and
[submission text draft](docs/DEVPOST_SUBMISSION.md). Nothing is deployed or
automatically submitted to Devpost.

## Prerequisites

- Python **3.11** with `venv` and SQLite FTS5; Git for cloning. Python 3.12+ is
  outside the declared supported range. Windows PowerShell was used for verification.
- Internet access for initial dependency installation; later document search,
  quizzes and local-model inference can run without a remote API.
- For AI answers: separately installed [Ollama](https://docs.ollama.com/quickstart)
  and an installed generation model. The tested machine has approximately 16 GB
  RAM and uses CPU inference. Available memory affects latency and reliability.
- Qwen3 4B uses approximately 2.50 GB for the installed quantized model file;
  runtime memory is additional. Check free disk/RAM before downloading a model.

## Install and run (Windows PowerShell, Python 3.11)

For a fresh checkout, run
`git clone https://github.com/AkhileshSelvan/tutortrace-ai.git` and change into
the cloned directory. Substitute that location for `D:\tutortrace-ai` below.

Run from this repository. The default `python` on the development machine is 3.14;
use the explicit virtual-environment interpreter below.

```powershell
cd D:\tutortrace-ai
py -3.11 -m venv .venv
New-Item -ItemType Directory -Force data\tmp,data\pip-cache | Out-Null
$env:TEMP = "$PWD\data\tmp"
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = "$PWD\data\pip-cache"
.\.venv\Scripts\python.exe -m ensurepip
.\.venv\Scripts\python.exe -m pip install --timeout 120 -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

For the existing prepared environment, just run the last command. Open
[the local application](http://127.0.0.1:8501). It binds to loopback only.
`requirements.txt` pins the dependency versions used during verification;
`pyproject.toml` declares package metadata and dependency families.

1. Choose **Load sample course**, or upload your own `.pdf` / `.pptx` and select
   **Ingest documents**. Multiple files are processed independently.
2. Check the library, ingestion history, and extraction warnings.
3. Search `kinetic`, `gravitational`, `isolated`, or `watts` for sample evidence.
4. Inspect the citation to see the source text, IDs and character offsets.
5. Preview an original PDF page. For PowerPoint, download the original and open
   the displayed slide number in a presentation viewer.

## AI Tutor

Start the installed Ollama service (`ollama serve` if it is not already running).
The verified local defaults use **qwen3:4b** for generation and, optionally,
**nomic-embed-text:latest** for semantic retrieval. Check `ollama list` first;
missing models produce an explicit error, never an automatic download. CPU
inference works on the tested 16 GB machine but can take tens of seconds.

After installing Ollama, run `ollama list`. If `qwen3:4b` is absent and your
resources permit it, explicitly run `ollama pull qwen3:4b`. Optional semantic
retrieval requires `ollama pull nomic-embed-text`; it is unnecessary for the
recommended keyword-only demo. Downloads are operator actions, never automatic
application behavior. Do not start a second `ollama serve` if the service is
already running. Keep the service running while using AI Tutor.

1. Open **AI Tutor** below the library and search interface.
2. Use **Check model status**. This checks installation, not a guarantee of enough
   memory or successful inference.
3. Select one or several documents as a course; empty selection searches all.
4. Ask a question and inspect each statement's source and exact supporting quote.
5. Open the cited physical PDF page, or download the PPTX and open the shown slide.

The model can cite only evidence supplied for that question. Invalid IDs, invented
quotes, malformed responses and contradictory response structures are rejected.
If the model explicitly abstains but emits accompanying claims, all those claims
and citations are withheld and the UI says so.
Empty retrieval always abstains; the model is instructed to abstain when selected
evidence cannot answer. Inference failures show an error with retrieved excerpts
available for inspection. **Valid citations and quotes do not prove that
every generated claim follows logically from them.** Inspect the evidence.

Semantic retrieval is opt-in. It combines keyword and embedding ranks, suppresses
redundant windows, and respects the selected documents and context limits. Its
separate local embedding cache is ignored by Git; the source database stays at
schema 2. If embeddings fail, the UI explicitly reports keyword-only fallback.

## Adaptive practice

1. In **Adaptive practice**, create a local learner profile. Profiles separate
   progress but are **not authenticated accounts**.
2. Select a document/course, enter topic keywords appearing together in the source
   (for example `energy`), choose formats and a difficulty, and generate a quiz.
3. The first objectively graded practice in each topic/course is diagnostic.
   **Adaptive** starts easy; a manually selected level overrides this choice.
4. Answer the multiple-choice, exact-wording short-answer, or numerical recall
   questions, then select **Grade assessment**. Expand each answer for its key,
   supporting statement, physical page/slide and original source.
5. Inspect the topic dashboard, revision priorities and learning history/chart.
   **Revise with AI tutor** prepares a question and selects the matching documents;
   **Ask AI tutor** runs the configured model. Explicitly stated prerequisites are
   shown when the source contains them; other relationships are not inferred.
6. Restart the app and select the same learner. Unfinished quizzes, submissions,
   estimates, and previous answer reviews are retained.

Assessment generation and grading are deterministic, with **no model call**.
These are source-cloze **recall** exercises, not unrestricted LLM-generated
questions or a validated measure of understanding. Numerical questions recall a
stated value; they do not independently verify the source's calculation. Every
question and key is rebuilt from provenance-checked source text before use.
An unsupported or stale question fails closed. Short answers with different
wording receive **needs review**, not an assumed semantic grade.

The transparent estimate is `(1 + correct) / (2 + correct + incorrect)`, a
Beta(1,1) count model of source-recall success. New topics start at 50% **unknown**.
Unverified short answers do not update it. This is not calibrated knowledge
probability or Bayesian Knowledge Tracing. Adaptive levels change the number of
MCQ options, missing text length, or numerical hints; they are not psychometrically
calibrated. Recent facts from the last two issued quizzes are excluded, including
abandoned quizzes. Unseen facts are preferred; limited material may yield fewer
questions or explicit exhaustion. Practice is open-book.

Learner data uses `data/tutortrace.learning.sqlite3` (schema 1), separate from the
unchanged source ledger (schema 2). Keep **both** databases when backing up or
moving the course and its progress. Re-indexing can retire old chunk IDs;
historical grades remain, but a retired citation is flagged instead of silently
rebound to different evidence. See the [learning architecture](docs/LEARNING_MODEL.md).

Reproduce the assessment evaluation and complete restart smoke test:

```powershell
.\.venv\Scripts\python.exe -m scripts.evaluate_learning
.\.venv\Scripts\python.exe -m scripts.learning_smoke
# Optional: one bounded real-model revision call; requires installed/running Ollama.
.\.venv\Scripts\python.exe -m scripts.learning_smoke --real-model --output docs/evaluation/m3-real-revision.json
```

The three scripted learners completed 27/27 quizzes and 81/81 answers with 0/81
repeated facts in the recorded run. Their prescribed answer patterns test software
behavior; changing estimates are **not evidence of real-student learning gains**.

Configuration is through shell environment variables; `.env.example` is a reference,
not an automatically loaded configuration file. To select an existing local model:

```powershell
$env:TUTORTRACE_LLM_PROVIDER = 'ollama'
$env:TUTORTRACE_LLM_MODEL = 'qwen3:4b'
$env:TUTORTRACE_TIMEOUT = '120'
.\.venv\Scripts\python.exe -m streamlit run app.py
```

For a remote provider, set `TUTORTRACE_LLM_PROVIDER=openai-compatible`,
`TUTORTRACE_LLM_URL` to its HTTPS API base ending in `/v1`, `TUTORTRACE_LLM_MODEL`,
and `TUTORTRACE_API_KEY` through your shell or secret manager. The endpoint must
support `/chat/completions`, `max_tokens` and JSON-object responses. Asking a
question then sends that question and selected excerpts to the configured service.
ChatGPT Plus / Claude Pro subscriptions do not imply API access. This remote
adapter is covered by deterministic contract tests; a live remote service has
not been verified with credentials in this milestone.

## Verify

Release verification on **14 October 2026** reran the complete suite:
**216 passed in 88.82 seconds**, zero failures/skips. Ingestion and learning smoke
checks passed, a fresh Streamlit server returned HTTP 200, and one real Qwen3 4B
revision call answered in **70.54 seconds**. The recorded M2 diagnostic set
recovered all 14/14 labelled source units, with selected-source precision 14/21;
these are small-set observations, not general accuracy guarantees. The M3
simulation completed 27/27 sessions and 81/81 answers with zero repeated facts.
See [final evaluation](docs/FINAL_EVALUATION.md) for denominators, configurations,
separation of mocks/simulations/real inference, and machine-readable records.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m scripts.smoke_test
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m scripts.evaluate_tutor --output data\retrieval-evaluation.json
.\.venv\Scripts\python.exe -m scripts.evaluate_tutor --real --output data\real-evaluation.json
.\.venv\Scripts\python.exe -m scripts.evaluate_tutor --hybrid --output data\hybrid-evaluation.json
.\.venv\Scripts\python.exe -m scripts.real_model_smoke --hybrid
```

Tests generate small educational PDF/PPTX fixtures. The smoke test ingests the
committed sample files into a temporary repository-local database, reopens it,
and asserts source bytes, duplicates, search results and all four locations.
Streamlit's AppTest exercises the real app, file-upload batches (including failures
and duplicates), sample ingestion, search, citation inspection and PDF rendering.
It does not simulate an operating-system file picker.

## Data and provenance

- Default database: `data/tutortrace.sqlite3`, ignored by Git. Source files are
  stored as BLOBs in SQLite so originals and the search index commit atomically.
- Optional `TUTORTRACE_DATA_DIR` shell variable selects the data directory.
  `.env.example` documents it; the app does not automatically load `.env` files.
- SHA-256 of original bytes identifies a document; renaming a file does not
  duplicate it. Different bytes with the same filename remain separate documents.
- Source units retain one-based **physical** PDF page / PPTX slide numbers,
  including blanks. PDF-defined page labels are displayed alongside physical
  pages, for example `chapter.pdf — PDF page 3 (label: 1)`. Labels are never
  guessed from printed text; PDFs without label metadata use physical pages only.
- Chunks never span pages/slides. Their stable IDs include the unit ID,
  pipeline version, normalized text and character offsets.
- Evidence is verified against its document's persisted pipeline version. Older
  evidence remains searchable after an application upgrade. Re-uploading identical
  bytes from an older pipeline atomically replaces its extraction and index while
  preserving the document ID, original, filename and original ingestion time.
  Current-version duplicates leave evidence unchanged and only log the attempt.
- Database schema 1 upgrades automatically to schema 2 using transactional
  `PRAGMA user_version` migrations. Migration preserves existing text and IDs;
  re-upload is needed to apply new extraction and populate older PDF page labels.
- PDF extraction expands ligatures and joins letter continuations at line-end
  hyphens within a text block. Original bytes remain unchanged; unusual layouts
  and genuinely hyphenated compounds still need source inspection.
- Search uses SQLite FTS5 and BM25 keyword ranking. Results are passages, not
  generated answers, semantic matches, or probabilities of correctness.
  Queries use the same `unicode61` tokenizer as the index, avoiding Python
  casefold mismatches. This is not complete multilingual or transliteration support.
- Valid files with no extracted text have `empty` status: originals and metadata
  are preserved, but no passages are indexed. Invalid uploads record failure
  metadata; their bytes are not retained. If storage itself fails, history cannot
  be guaranteed and the error is surfaced immediately.

Only upload material you are entitled to use. This local prototype has no accounts,
access controls, encrypted database, or multi-tenant isolation. Private uploads,
local databases, credentials and environments are excluded from source control.

## Design and review

- [Final architecture](docs/FINAL_ARCHITECTURE.md)
- [Final evaluation and release checks](docs/FINAL_EVALUATION.md)
- [Reproducible demonstration](docs/DEMO_SCRIPT.md)
- [Devpost submission draft — not submitted](docs/DEVPOST_SUBMISSION.md)

- [Architecture](docs/ARCHITECTURE.md)
- [Known limitations](docs/KNOWN_LIMITATIONS.md)
- [Verification record and review handoff](docs/MILESTONE_1_VERIFICATION.md)
- [Milestone 1 audit fixes and verification](docs/MILESTONE_1_AUDIT_FIX_VERIFICATION.md)
- [Milestone 2 verification and evaluation](docs/MILESTONE_2_VERIFICATION.md)
- [Milestone 3 verification and evaluation](docs/MILESTONE_3_VERIFICATION.md)
- [Assessment verification and learner model](docs/LEARNING_MODEL.md)
- [AI assistance and third-party attribution](docs/AI_DISCLOSURE.md)
- [Sample material provenance](demo_assets/README.md)
- [Original project blueprint](docs/TutorTrace_AI_First_Place_Blueprint.md)

The blueprint describes the broader product goal. It is not a claim that later
milestones or competition acceptance gates are complete.

## Known limitations

No video/audio ingestion, OCR, diagram understanding, semantic grading, calibrated
mastery, or measured real-student learning gains. PDF/PPTX support extracts text;
it is not multimodal reasoning. Source validity does not guarantee claim truth.
Numerical practice recalls stated values, and short-answer paraphrases need review.
Local inference may be slow or fail; remote-provider integration has contract
tests but no live credential-backed evaluation. Profiles have no authentication.
See [the full limitations](docs/KNOWN_LIMITATIONS.md).

## AI assistance, credits and licenses

Built by Akhilesh Selvan with OpenAI Codex assistance for implementation, tests,
synthetic materials and documentation. Runtime tutoring uses the configured model;
test mocks are not application answers. No independent Claude Code audit is claimed.
See [AI disclosure](docs/AI_DISCLOSURE.md).

Original demo assets and explicitly identified synthetic evaluation content are
CC0 1.0. **No repository-wide code license has been selected:** public visibility
must not be represented as an open-source license grant. Dependency/model licenses
remain separate. PyMuPDF uses AGPL/commercial licensing; other components and
upstream notices are listed in [third-party notices](docs/THIRD_PARTY_NOTICES.md).
The owner must resolve the intended code license and applicable distribution
obligations; this release does not certify license compliance or event eligibility.
