# TutorTrace AI

Track D — Personalized Tutoring & Adaptive Learning, Multimodal AI Hackathon 2026.

**Milestone 1:** a local PDF/PPTX evidence library. Upload educational materials,
search extracted text, inspect exact page/slide citations, preview PDF pages, and
download the byte-identical original. No LLM, API key, GPU, or paid service is needed.
Tutoring, assessments, mastery tracking, video ingestion and visual understanding
are future milestones, not current features.

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

## Verify

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m scripts.smoke_test
.\.venv\Scripts\python.exe -m pip check
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
- [AI assistance and third-party attribution](docs/AI_DISCLOSURE.md)
- [Sample material provenance](demo_assets/README.md)
- [Original project blueprint](docs/TutorTrace_AI_First_Place_Blueprint.md)

The blueprint describes the broader product goal. It is not a claim that later
milestones or competition acceptance gates are complete.
