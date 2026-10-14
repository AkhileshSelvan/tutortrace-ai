# TutorTrace AI

Track D — Personalized Tutoring & Adaptive Learning, Multimodal AI Hackathon 2026.

**Milestone 2:** a PDF/PPTX evidence library and source-grounded AI tutor. Upload educational materials,
search extracted text, inspect exact page/slide citations, preview PDF pages,
download the byte-identical original, and ask a configured model questions about
selected documents. Retrieval alone needs no model or API key. Local AI uses
Ollama; remote inference requires separately supplied API credentials.
Assessments, mastery tracking, video ingestion and visual understanding remain
future milestones.

## Install and run (Windows PowerShell, Python 3.11)

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

- [Architecture](docs/ARCHITECTURE.md)
- [Known limitations](docs/KNOWN_LIMITATIONS.md)
- [Verification record and review handoff](docs/MILESTONE_1_VERIFICATION.md)
- [Milestone 1 audit fixes and verification](docs/MILESTONE_1_AUDIT_FIX_VERIFICATION.md)
- [Milestone 2 verification and evaluation](docs/MILESTONE_2_VERIFICATION.md)
- [AI assistance and third-party attribution](docs/AI_DISCLOSURE.md)
- [Sample material provenance](demo_assets/README.md)
- [Original project blueprint](docs/TutorTrace_AI_First_Place_Blueprint.md)

The blueprint describes the broader product goal. It is not a claim that later
milestones or competition acceptance gates are complete.
