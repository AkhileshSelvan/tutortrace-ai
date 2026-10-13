# Milestone 1 audit fixes — verification and review handoff

Verified locally on **13 October 2026 (IST)** in `D:\tutortrace-ai`.
Starting commit: `317a0f20fd4c76c1b05774a0e4c8ef2cf63a443d`, branch `main`,
clean working tree, one local commit ahead of `origin/main`.
This work is limited to the requested Milestone 1 audit corrections. Milestone 2,
deployment, Devpost submission and model inference were not performed.

## Confirmed baseline defects

Before edits, synthetic PDF/PPTX probes reproduced:

| Finding | Observed baseline behavior |
| --- | --- |
| H1 pipeline compatibility | Changing `models.PIPELINE_VERSION` made previously indexed evidence raise `ProvenanceError`; uploading the same bytes returned a duplicate and left it broken. |
| PDF line-end hyphenation | A PDF containing `Photo-` followed by `synthesis` on the next line returned no result for `photosynthesis`. |
| PDF page labels | Physical page 3 with PDF-defined label `1` displayed only `labels.pdf, page 3`; schema 1 had no label field. |
| Query normalization | `Straße` found zero results through application search but one through a direct FTS query using the original term. Python full casefold produced `strasse`, which disagrees with SQLite `unicode61`. |
| Migration foundation | The existing database used schema 1, with no migration path. |

The original suite passed **59 tests in 27.03s** before changes. Passing that suite
did not cover the reproduced audit defects.

## Implemented corrections

- Chunk integrity verification now explicitly uses the owning document's persisted
  pipeline version. Unit IDs, chunk hashes, substring/offset checks and original
  byte hashes remain enforced. Changing the current version alone does not invalidate
  existing evidence.
- Re-uploading an older pipeline's source performs extraction first, then replaces
  units, chunks, FTS entries, document extraction metadata and success history in
  one `BEGIN IMMEDIATE` transaction. Original bytes, document ID, first filename
  and first ingestion timestamp are preserved. The expected old version is checked
  again under the write lock, preventing a stale extraction from overwriting an
  intervening version. Same-version duplicates only add an attempt record.
- Extraction pipeline version is now
  `text-v2:pdf-dehyphenate-expand-ligatures-labels:chars-1200:overlap-150`.
  Successful re-indexing replaces old chunk IDs; document IDs stay stable.
- PDF extraction enables `TEXT_DEHYPHENATE` and clears
  `TEXT_PRESERVE_LIGATURES`. In PyMuPDF 1.28.2, the flag alone retained the
  hyphen/newline in the synthetic plain-text output. A bounded fallback therefore
  joins letter continuations within each sorted text block, before whitespace
  normalization. It does not join separate blocks or pages. The fixture containing
  actual `ﬁ` and `ﬂ` characters extracts searchable `office` and `flow`.
- Optional labels come from `page.get_label()` and are stored per physical PDF
  page, including blank pages. A labeled citation is
  `chapter.pdf — PDF page 3 (label: 1)`. Unlabeled PDFs retain physical-page
  citations, and PPTX retains slide citations. No printed-text label inference.
- Query terms now come from a temporary SQLite FTS5 table and `fts5vocab`, using
  the same `unicode61` configuration as the persistent index. Literal quoting,
  parameterized SQL, bounded queries and English stopword filtering remain.
- Schema 2 adds nullable `units.page_label`. Schema creation, upgrade DDL and
  `PRAGMA user_version` changes are transactional. Startup rereads the version
  under the writer lock, preserves schema-1 data and rejects unknown schemas.
- Concurrent migration testing exposed a WAL initialization busy/locked race.
  Startup now retries those specific SQLite errors within a bounded wait.

## Database compatibility and failure verification

`tests/fixtures/schema_v1.sql` freezes the original schema from the base commit.
Tests construct genuine version-1 rows with independently computed legacy hashes,
self-created PDF bytes, blank units and ingestion history. They do not initialize
the legacy fixture through the new migration code.

Verified behaviors:

- Schema 1 becomes schema 2 without changing original bytes, old text, chunk IDs
  or pipeline versions. Missing labels stay null until re-upload. Existing evidence
  remains searchable/resolvable; repeated startup adds no further columns or rows.
- New databases reach schema 2. Concurrent initialization and four concurrent
  upgrade uploads succeed; exactly one re-index and three duplicates are observed.
- A deliberate SQL failure after migration DDL rolls back the column and version.
  Failure during fresh creation rolls back all schema objects to version 0.
- A SQL trigger failure after re-indexing has begun restores all old document,
  unit, chunk and history rows. FTS5 external-content integrity checks pass.
- A separate Python process exits with code **23** from a SQLite trigger during
  re-index insertion. Reopening the database finds the old rows/index intact.
- A fresh process after successful upgrade retrieves physical page 3, label `1`,
  the current persisted pipeline version and the correct original SHA-256.
- Changed legacy chunk text/offsets or a forged persisted pipeline version still
  raise `ProvenanceError`. A corrupted original prevents re-indexing.

## Executed commands and outcomes

All Python commands used the repository's existing virtual environment:
Python **3.11.17**, SQLite **3.53.1**, Streamlit **1.65.0**, PyMuPDF **1.28.2**,
python-pptx **1.0.2**, pytest **9.1.1**. Dependencies were unchanged.

```powershell
git status --short --branch
git log -3 --oneline --decorate
.venv\Scripts\python.exe --version
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m pytest -q tests/test_audit_regressions.py
.venv\Scripts\python.exe -m scripts.smoke_test
.venv\Scripts\python.exe -m pip check
git diff --check
git fetch origin
git rev-parse origin/main
```

| Check | Actual outcome |
| --- | --- |
| Baseline suite, before edits | 59 passed in 27.03s |
| Original suite, after primary fixes | 59 passed in 69.69s |
| First audit regression run | 26 passed, 1 failed: concurrent startup hit `database is locked` while enabling WAL |
| Audit regressions after WAL fix and additional coverage | 31 passed in 20.60s |
| Final complete suite | **90 passed in 67.93s; no failures or skipped tests** |
| Ingestion smoke test | PASS: two originals, two duplicate checks, four exact source locations, reopened database and no-match search |
| Dependency consistency | `No broken requirements found.` |
| Diff whitespace check | Passed; Git emitted only Windows LF/CRLF conversion notices |
| Remote read | Fetch succeeded; `origin/main` was `f288a24e31d16d3624096315574d9a73cc683fa3`, an ancestor of the local base |

The recorded durations are test-run observations, not performance benchmarks.
Local pytest outputs are saved in ignored `data/audit-baseline-pytest.log`,
`data/audit-working-pytest.log`, `data/audit-regressions.log` and
`data/audit-final-pytest.log`. The regression log contains the final passing run.

The end-to-end smoke test verified:

| Query | Exact citation |
| --- | --- |
| `kinetic` | `energy_notes.pdf, page 1` |
| `gravitational` | `energy_notes.pdf, page 2` |
| `isolated` | `energy_slides.pptx, slide 1` |
| `watts` | `energy_slides.pptx, slide 2` |

Streamlit was restarted with the final code using:

```powershell
.venv\Scripts\python.exe -m streamlit run app.py --server.headless true --server.address 127.0.0.1 --server.port 8501
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8501/_stcore/health
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8501/
```

Startup succeeded on loopback. Health returned **HTTP 200, `ok`**; the root page
returned **HTTP 200**. These HTTP checks establish server availability. Separately,
Streamlit AppTest exercised a real legacy upload, displayed the re-index success
message, searched `photosynthesis` and displayed the exact physical-page/label
citation without application errors. Existing app tests also passed. Native
browser file-picker/download interaction was not manually exercised.

## Regression coverage added

`tests/test_audit_regressions.py` adds 31 executed cases covering:

- Persisted-version provenance and future pipeline changes; atomic/idempotent
  upgrades, ordinary no-extraction duplicates, stale writers and concurrent uploads.
- Extraction failure, SQL failure, actual process interruption and fresh-process
  persistence after a successful upgrade.
- Old evidence text/offset corruption, forged version metadata and original-byte
  corruption.
- Version-1 upgrade, latest-schema creation, repeated/concurrent startup, migration
  rollback and refusal to overwrite an unknown unversioned schema.
- Split-word dehyphenation, actual ligature expansion, physical page boundaries,
  separate text blocks, inline compounds, blank-page labels and unlabeled pages.
- `Straße`, uppercase sharp-s, accented/decomposed Latin, Turkish dotted-I,
  Greek and Cyrillic examples. A negative test explicitly preserves the absence
  of `Straße`/`strasse` transliteration.
- Streamlit re-index status and labeled citation display.

## Changed files and source-control review

- `tutortrace/models.py`: versioned IDs, evidence pipeline and optional labels.
- `tutortrace/persistence.py`: migrations, version-aware integrity, transactional
  re-indexing and SQLite query tokenization.
- `tutortrace/ingestion/service.py`, `tutortrace/ingestion/pdf.py`: upgrade routing,
  extraction flags, bounded dehyphenation and PDF labels.
- `tutortrace/retrieval/chunking.py`, `tutortrace/retrieval/search.py`: explicit
  pipeline IDs and consistent query terms.
- `app.py`: re-index outcome and evidence pipeline display.
- `tests/test_audit_regressions.py`, `tests/fixtures/schema_v1.sql`: regression
  coverage and frozen legacy schema; documents are self-created at test runtime.
- `README.md`, `docs/ARCHITECTURE.md`, `docs/KNOWN_LIMITATIONS.md`,
  `docs/MILESTONE_1_VERIFICATION.md`, this document: current behavior and review record.

Changed source and tests were read and the diff reviewed. A credential-pattern
scan found no private-key, AWS access-key, GitHub-token or API-key candidates in
source-control-selected files. Runtime data/databases were excluded. Explicit
`git check-ignore --no-index` checks confirmed `.env`, `.streamlit/secrets.toml`,
`data/tutortrace.sqlite3`, `.venv/Scripts/python.exe` and `credentials-local.json`
remain ignored. No private educational material was added.

## Remaining limits and next milestone

No known failing case remains in the executed suite. The limits in
[KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) still apply: lexical retrieval only,
bounded dehyphenation ambiguity, PDF-metadata labels only, selected Unicode cases
rather than complete multilingual support, and no bulk re-index or schema downgrade.
Same-version duplicate uploads do not repair damaged evidence; old chunk IDs are
retired after successful re-indexing. No video, OCR, diagram interpretation,
generated tutoring, personalization or learning-outcome claims are made.

Ready for independent Claude Code review, particularly the transaction boundaries,
frozen legacy upgrade path and extraction fallback. That independent review has
not been performed by this implementation session. Recommend treating its review
as the Milestone 1 gate before starting the separately scoped Milestone 2.
