# Milestone 1 architecture

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

Future AnswerProvider ← question + retrieved Evidence
Future caller must validate returned chunk IDs through Store.resolve_evidence.
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
| `providers/llm.py` | Future inference contract only; no configured provider or generated answer |
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
  location, normalized extracted text. Blank pages/slides are recorded.
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

Schema version is stored in `PRAGMA user_version`. Unsupported versions are
rejected. Future schema/extractor changes require an explicit migration/reindex
strategy; silent mixed-version re-extraction is not implemented.

## Grounding boundary

The UI formats citations exclusively from ledger rows joined through chunk → unit
→ document. `resolve_evidence` accepts only a stored chunk ID. Reads verify the
unit ID, chunk ID and exact substring offsets. Original downloads and PDF previews
verify the source BLOB against its SHA-256 document ID. These checks catch accidental
corruption; they do not constitute a tamper-proof signed database or evaluate
whether a future model's claims follow logically from the evidence.

Reading order is PyMuPDF top-left text order for PDFs, and presentation shape order
for PPTX. Whitespace is normalized before chunking; offsets are into this text,
not PDF bytes, coordinates or XML offsets. The original is always available for
comparison. Every extraction records its visual-understanding limitations.

## Retrieval behavior

Queries are limited to 1,000 characters / 64 distinct substantive terms. Unicode
word tokens are individually quoted and OR-combined, then passed as SQL parameters.
Users cannot inject SQL or FTS operators. FTS5 BM25 orders evidence, with stable
document/location/offset tie-breaks. Optional document scoping and 1–50 result
limits are enforced. This is lexical retrieval; there is no semantic relevance
threshold, answer inference or automatic abstention judgement.

Primary implementation references: [SQLite FTS5](https://www.sqlite.org/fts5.html)
and [PyMuPDF text extraction](https://pymupdf.readthedocs.io/en/latest/app1.html).

## Input limits

50 MiB/file; 2,000 pages/slides; 5,000,000 extracted characters/file. PPTX packages
are checked for at most 10,000 entries and 200 MiB declared expanded size before
parsing. PDFs also have a 60-second processing timeout. These bounds help a local
demo but do not replace a full sandbox or process-level memory limits for public deployment.
