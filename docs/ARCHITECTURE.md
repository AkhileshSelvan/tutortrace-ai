# TutorTrace architecture — Milestone 3

The smallest viable design is a local Streamlit process plus SQLite and short-lived
PDF worker processes. No
server API, vector database, model downloads, credentials, or external services
are needed for ingestion and evidence retrieval.

```text
Streamlit app.py
  ├── ingestion.service → ingestion.pdf / ingestion.pptx
  │                        ↓ source units (including blanks)
  │                     retrieval.chunking
  │                        ↓ bounded text with source offsets
  ├── persistence.Store → SQLite ledger + originals + FTS5
  └── retrieval.search → ranked Evidence → source inspector / original preview

AI Tutor → retrieval.context → selected Evidence → AnswerProvider.complete
         → tutoring.validate_answer → claims with canonical source metadata
Optional semantic retrieval → local Ollama embeddings → disposable SQLite cache

Adaptive practice → retrieval.context → assessment.question_pool / verify_question
                  → learning.LearningStore → learner SQLite sidecar
                  → deterministic grades + atomic mastery/history update
Revision priorities → verified Evidence + learner-aware prompt → existing AI Tutor
```

## Module responsibilities

| Module | Responsibility |
| --- | --- |
| `models.py` | Immutable dataclasses and deterministic ID functions |
| `errors.py` | Typed, presentable validation, storage and provenance errors |
| `ingestion/pdf.py` | PyMuPDF page extraction and encryption checks |
| `ingestion/pdf_worker.py` | Isolated PDF extraction/rendering, called with a 60-second deadline |
| `ingestion/pptx.py` | Text boxes, recursive grouped shapes and table rows |
| `ingestion/service.py` | Type/size checks, hash duplicate detection and orchestration |
| `retrieval/chunking.py` | 1,200-character windows, up to 150 characters of overlap, per unit |
| `persistence.py` | SQLite schema, transactions, originals, history, FTS queries and evidence resolution |
| `retrieval/search.py` | Bounded literal search terms and common English stopword removal |
| `providers/llm.py` | Provider-neutral completion/status contract, configuration and typed failures |
| `providers/adapters.py`, `providers/http.py` | Real Ollama / OpenAI-compatible HTTP inference, bounded responses and safe errors |
| `retrieval/context.py` | Scoped retrieval, optional local embeddings, reciprocal-rank fusion, deduplication and context limits |
| `tutoring.py` | Question orchestration, structured output, per-claim citation and exact-quote validation |
| `tutor_ui.py` | Provider status, questions, explicit answer/abstention/error states and source inspection |
| `assessment.py` | Source-derived cloze questions, full key/stem verification and deterministic grading |
| `learning.py` | Learners, course/topic identity, cached questions, atomic sessions/attempts, estimates and revision |
| `learning_ui.py` | Diagnostic/practice quizzes, cited reviews, mastery dashboard, history/chart and tutor handoff |
| `app.py` | Uploads, status, library, retrieval, provenance and original inspection |

Standard-library dataclasses avoid adding Pydantic solely for internal records.
SQLite comes with Python; FTS5 is checked through actual schema creation. External
dependencies are the requested Streamlit, PyMuPDF, python-pptx and pytest. Their
transitive packages are locked in `requirements.txt`.

## Storage contract

- `documents`: SHA-256 ID, sanitized display filename, format, original BLOB,
  byte count, unit/chunk counts, indexed/empty status, warnings, UTC ingestion time,
  and extractor/chunker pipeline version.
- `units`: stable document/location-derived ID, parent document ID, one-based
  location, normalized extracted text, nullable PDF-defined `page_label`.
  Blank pages/slides are recorded; physical location remains canonical.
- `chunks`: stable pipeline/unit/offset/text-derived ID, parent unit ID, half-open
  offsets `[start, end)`, and exactly that substring of the unit text.
- `chunks_fts`: SQLite FTS5 external-content index. Triggers keep it in the same
  transaction as source chunks.
- `ingestion_attempts`: submitted display name, content hash, optional document ID,
  status, error code/message and UTC timestamp. A duplicate retains the first
  document's filename and logs the new upload name in this history.

Original bytes, unit records, chunks, index entries and the successful attempt
commit in one `BEGIN IMMEDIATE` transaction. A duplicate check inside that
transaction handles simultaneous sessions. WAL supports simultaneous readers;
writers wait up to 15 seconds. Connections close after each operation and no
connection is shared across Streamlit sessions.

PyMuPDF does not support multithreaded use. PDF extraction and preview therefore
run through `python -m tutortrace.ingestion.pdf_worker`, with raw bytes on stdin and
JSON on stdout. Workers never open the database. The parent enforces a 60-second
timeout, kills a timed-out child, and surfaces an explicit error before committing.
This also isolates concurrent sessions from native parser state. See the
[PyMuPDF multiprocessing guidance](https://pymupdf.readthedocs.io/en/latest/recipes-multiprocessing.html).

Schema version is stored in `PRAGMA user_version`. Fresh databases bootstrap the
original schema and migrate to version 2 in one transaction. Schema 1 upgrades
with `ALTER TABLE units ADD COLUMN page_label TEXT`, preserving all old rows and
IDs. Each migration and its version update run under `BEGIN IMMEDIATE`; startup
rechecks the version after acquiring the lock. SQL statements are executed
individually because `executescript` would implicitly commit. Concurrent WAL
initialization retries SQLite busy/locked errors within a bounded wait. Unknown
nonempty unversioned databases and unsupported future versions are rejected.

Schema upgrades do not re-extract. Ingestion captures the current pipeline version
and compares it with the persisted document version. Matching versions only log
a duplicate attempt. Different versions extract before taking the writer lock,
then atomically replace units, chunks and FTS entries and update document metadata.
The original bytes, document ID, filename and ingestion timestamp are retained.
The transaction rechecks the expected old version to reject stale writers; another
writer already at the requested version is treated as a duplicate. Failure or
process exit before commit preserves the complete old evidence. Re-indexing
retires old chunk IDs and records its version change in ingestion history.

## Grounding boundary

The UI formats citations exclusively from ledger rows joined through chunk → unit
→ document. `resolve_evidence` accepts only a stored chunk ID. Reads verify the
unit ID, chunk ID (using the document's persisted pipeline version) and exact
substring offsets. Original downloads and PDF previews
verify the source BLOB against its SHA-256 document ID. These checks catch accidental
corruption; they do not constitute a tamper-proof signed database or evaluate
whether a future model's claims follow logically from the evidence.

Reading order is PyMuPDF sorted text-block order for PDFs, and presentation shape
order for PPTX. PDF extraction enables `TEXT_DEHYPHENATE` and disables
`TEXT_PRESERVE_LIGATURES`. In the verified PyMuPDF version, plain block output
can retain line-end hyphens even with that flag, so a bounded fallback joins
hyphen/newline sequences between letters within each block. It never joins
blocks or physical pages. `page.get_label()` supplies optional PDF-defined labels;
no printed labels are inferred. Whitespace is normalized before chunking; offsets are into this text,
not PDF bytes, coordinates or XML offsets. The original is always available for
comparison. Every extraction records its visual-understanding limitations.

## Retrieval behavior

Queries are limited to 1,000 characters / 64 distinct substantive terms. A
connection-local temporary FTS5 table and `fts5vocab` produce query terms using
the index's exact `unicode61` configuration, including its case and diacritic
normalization. Python full casefold is not applied. Terms are deduplicated in
source order, filtered for English stopwords, individually quoted and OR-combined,
then passed as SQL parameters.
Users cannot inject SQL or FTS operators. FTS5 BM25 orders evidence, with stable
document/location/offset tie-breaks. Optional document scoping and 1–50 result
limits are enforced. This is lexical retrieval; there is no semantic relevance
threshold in the original search interface. The separate tutor context selector
builds on this unchanged search behavior.

## Tutor and provider boundary

The tutor accepts a question, optional document IDs, a context configuration and
a provider. FTS results retain their existing source objects. Optional semantic
retrieval scans at most 500 passages by default (configurable up to 5,000), embeds
with the local model and filters cosine similarity below 0.35. It refuses to
silently scan a truncated corpus; oversized scopes fall back to keyword retrieval
with a warning. Reciprocal-rank fusion uses `1 / (60 + rank)`. Redundant windows
within the same source unit are suppressed; identical text in distinct sources
remains attributable to each source. Defaults select at most five complete chunks
and 3,600 source characters. These are character limits, not exact token counts.

Embeddings live in a separate `<ledger>.embeddings.sqlite3` cache keyed by model
identity/digest, chunk ID and text hash. Re-indexed chunk IDs and changed model
digests cannot reuse old entries. Unused historical entries are not automatically
pruned. Vectors never replace canonical source metadata. The source ledger's
schema and pipeline version remain unchanged at M1.1 values.

The model receives the question, excerpts, request-local aliases `E1`, `E2`, etc.,
and a JSON response schema. Aliases map only to this question's immutable evidence
snapshot. It returns short claims with supporting aliases and exact quotes,
unsupported aspects, and answered/abstained/conflict status. The system prompt
treats source text and user questions as untrusted data and prohibits filling gaps
from general knowledge. This is mitigation, not a proof of prompt-injection immunity.

Before display, the validator rejects unknown aliases, invented excerpts, missing
support, invalid structure and inconsistent status. Each cited chunk is resolved
again through the existing provenance verifier and compared with its snapshot,
detecting re-indexing or changed metadata during inference. Citation names,
physical locations, labels and downloads come only from ledger records. A conflict
requires at least two distinct cited passages. Citation validity is deliberately
not presented as semantic entailment verification.

An explicit model abstention is conservative: any accompanying claims and their
citations are withheld in full, with a visible explanation. They are never
reinterpreted as an answer. The strict validator still checks the retained
structure and every claim that could actually be displayed.

Ollama runs locally with temperature 0, seed 17, thinking disabled, bounded output,
4,096 context tokens and a 120-second socket timeout by default. Installed cloud
aliases are rejected by the local adapter. No automatic model downloads or provider
switches occur. The remote adapter requires explicit HTTPS configuration and an
API credential. Redirects are rejected, local HTTP bypasses proxies, response size
is bounded, and provider error bodies/credentials are not shown. Remote compatibility
varies by service; live remote inference has not been credential-tested here.

No retrieval results means deterministic abstention without inference. Model
abstention is distinguished from provider or validation failure. Failures never
produce substitute answers. The app stores the current answer in its Streamlit
session only; source and embedding persistence are independent of chat state.

Primary implementation references: [SQLite FTS5](https://www.sqlite.org/fts5.html)
and [PyMuPDF text extraction](https://pymupdf.readthedocs.io/en/latest/app1.html).

## Input limits

50 MiB/file; 2,000 pages/slides; 5,000,000 extracted characters/file. PPTX packages
are checked for at most 10,000 entries and 200 MiB declared expanded size before
parsing. PDFs also have a 60-second processing timeout. These bounds help a local
demo but do not replace a full sandbox or process-level memory limits for public deployment.

## Persistent adaptive practice

The learner sidecar has its own transactional `PRAGMA user_version=1` bootstrap;
the source schema, FTS index, extraction pipeline and tutor contracts are unchanged.
Question records reference immutable chunk IDs. Every issued/graded question is
reconstructed from the current canonical evidence and compared in full, including
its prompt, key, options, offsets, difficulty and deterministic ID. This is stronger
than accepting a model-supplied key with a valid citation. It verifies a bounded
source transformation, not the scientific truth of the original source.

Each grading transaction validates all responses before appending attempts,
updating topic counters and closing the session. SQLite rollback covers all three.
An ownership check and a unique open-session index prevent cross-profile grading
and concurrent duplicate assessments. Question identity is checked against both
the bank and assignment records. The source database is independently read-only
during practice; there is no distributed transaction between the two files.

See [LEARNING_MODEL.md](LEARNING_MODEL.md) for formulas, thresholds, diagnostic
behavior, cache invalidation, repetition policy and precise grading limitations.
