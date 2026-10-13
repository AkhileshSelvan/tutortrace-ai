# Milestone 1 verification and independent-review handoff

Verified locally on **13 October 2026 (IST)** in `D:\tutortrace-ai`.
Implementation and verification completed within the requested approximately
two-hour timebox. No remote push, deployment, Devpost action, paid API call or
external model inference was performed.

## Initial inspection

Commands: `Get-Location`, `git status --short --branch`, `git ls-files`, `rg --files`,
`py -0p`, `python --version`, `py -3.11 --version`,
`.\.venv\Scripts\python.exe --version`, and reads of the README, `.gitignore`,
coding prompt, blueprint, and `.venv/pyvenv.cfg`.

- Starting commit: `f288a24` (`chore: initialize TutorTrace AI`), branch `main`.
- Only README and `.gitignore` were tracked. The supplied coding prompt and blueprint
  were untracked; both were read and are now included without content edits.
- No existing application code or `AGENTS.md` was found in the repository.
- Shell-default Python was 3.14.7. The preexisting isolated `.venv` was Python
  **3.11.17**, with no pip initially. All final verification used that environment.
- The configured Git remote was inspected but was not used for any write.

## Dependency setup: actual commands and outcomes

The following environment settings kept installer cache and temporary writes in
the repository:

```powershell
New-Item -ItemType Directory -Force data\tmp,data\pip-cache | Out-Null
$env:TEMP = 'D:\tutortrace-ai\data\tmp'
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = 'D:\tutortrace-ai\data\pip-cache'
.\.venv\Scripts\python.exe -m ensurepip
```

Outcome: pip 24.0 and setuptools 79.0.1 installed into `.venv`.

```powershell
.\.venv\Scripts\python.exe -m pip install 'streamlit>=1.50,<2' 'PyMuPDF>=1.26,<2' 'python-pptx>=1.0.2,<2' 'pytest>=8.4,<10'
```

Outcome: **failed** with a `files.pythonhosted.org` read timeout. A retry with
`--timeout 120 --retries 5 --progress-bar off` stalled downloading a wheel and was
stopped before installation. This is a recorded setup failure, not a passing check.
The existing `uv` installer was then used:

```powershell
$env:UV_CACHE_DIR = 'D:\tutortrace-ai\data\uv-cache'
uv pip install --python .venv\Scripts\python.exe 'streamlit>=1.50,<2' 'PyMuPDF>=1.26,<2' 'python-pptx>=1.0.2,<2' 'pytest>=8.4,<10'
.\.venv\Scripts\python.exe -m pip freeze | Set-Content -Encoding utf8 requirements.txt
.\.venv\Scripts\python.exe -m pip install --no-index -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

Outcome: **46 packages installed**. Installing from the captured lock with
`--no-index` confirmed all 46 pinned requirements were already satisfied;
`pip check` returned **No broken requirements found.** This was not a second fresh
environment installation. The final project metadata requires Streamlit >=1.65
because its upload-widget test API is used by the suite.

| Component | Verified version |
| --- | --- |
| Python | 3.11.17 |
| SQLite | 3.53.1, FTS5 table creation executed successfully |
| Streamlit | 1.65.0 |
| PyMuPDF | 1.28.2 |
| python-pptx | 1.0.2 |
| pytest | 9.1.1 |

The full environment dependency versions are in `requirements.txt`. Local setup
logs are in ignored `data/install.log`, `data/uv-install.log` and
`data/locked-install.log`.

## Automated checks

```powershell
.\.venv\Scripts\python.exe -m compileall -q tutortrace scripts tests app.py
.\.venv\Scripts\python.exe -m scripts.create_demo_assets
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m scripts.smoke_test
```

- Compilation: exit 0.
- Fixture generation: `energy_notes.pdf`, **1,551 bytes**, 2 pages;
  `energy_slides.pptx`, **29,332 bytes**, 2 slides. These are original, tiny
  educational fixtures with provenance documented in `demo_assets/README.md`.
- Initial pytest run: **57 passed, 1 failed in 31.47s**. The app preview rendered,
  but the test queried the old raw `imgs` element name. Inspection of the installed
  Streamlit test tree showed the supported element name is `image`. The assertion
  was corrected; no app error was hidden or skipped.
- After that correction: **58 passed in 23.87s**.
- An additional real upload-widget batch test closed the remaining upload UI
  coverage gap. **Final run: 59 passed in 25.51s, zero failed, zero skipped.**
- Smoke test: exit 0, original bytes, duplicate checks, reopened persistence,
  source offsets, citation resolution and four exact locations all verified.

These elapsed test-run times are execution records, not retrieval-performance or
learning-quality benchmarks. No external RAG benchmark or model metric was run.

Coverage includes PDF pages, PPTX slides, blank locations, grouped shapes/tables,
empty and zero-byte files, unsupported and corrupt files, encrypted PDFs, file
type mismatch, upload/extraction/archive bounds, original-byte preservation,
renamed and concurrent duplicates, deterministic IDs, chunk overlap/coverage,
ranked and scoped search, hostile query syntax, separate-process restart,
unknown and tampered provenance, atomic rollback, database corruption/version
errors, PDF worker failure/timeout handling, and exact page preview.

Three Streamlit AppTest scenarios exercise sample ingestion/search/restart/preview,
empty uploads/no matches, and real PDF/PPTX upload batches with a corrupt file and
a renamed duplicate. Native browser file pickers and downloads were not automated.
The timeout test injects `TimeoutExpired`; it does not deliberately hang a real
native parser for 60 seconds.

The final full test output is retained in ignored `data/pytest.log`. Smoke output
is retained in ignored `data/smoke.log` and summarized below for review portability.

## Real ingestion smoke evidence

| Query | Actual citation returned | Actual passage fact |
| --- | --- | --- |
| `kinetic` | `energy_notes.pdf, page 1` | 2 kg at 3 m/s gives 9 joules |
| `gravitational` | `energy_notes.pdf, page 2` | 1 kg raised 2 m gains 19.6 joules with g=9.8 |
| `isolated` | `energy_slides.pptx, slide 1` | Total energy remains constant in an isolated system |
| `watts` | `energy_slides.pptx, slide 2` | 120 joules over 6 seconds gives 20 watts |

The query `photosynthesis` returned no evidence in this energy sample corpus.
Both reuploads were duplicates; reopening SQLite retained exactly two documents.
This checks those particular fixture cases, not a general retrieval-quality score.

Source SHA-256 IDs for the committed sample files:

```text
energy_notes.pdf
f011c3e9094ba108cbcbeef5de107683b4e87c48b5b9e56b93421a6bca76b13b

energy_slides.pptx
1d9a315d43cfc9306b65a4e2a16db9b5b4a5a83b8d1833bbaa588c71c5e4649e
```

## Actual application launch

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.headless true --server.address 127.0.0.1 --server.port 8501
Invoke-WebRequest -Uri 'http://127.0.0.1:8501/_stcore/health' -TimeoutSec 10
Invoke-WebRequest -Uri 'http://127.0.0.1:8501/' -TimeoutSec 10
Get-NetTCPConnection -LocalPort 8501 -State Listen
```

Outcomes: server started successfully; **health HTTP 200 `ok`**; **main page HTTP
200, 6,463 bytes**; listener verified on **127.0.0.1:8501**. Script behavior was
separately exercised by AppTest. The app is left running in a managed local session.
An initial attempt to use `Start-Process -WindowStyle Hidden` was rejected by
automatic approval review with `blocked by policy`; direct managed execution above
succeeded. No deployment or permission change was needed.

## Final change inventory

- Modified: `.gitignore`, `README.md`.
- Added configuration: `.gitattributes`, `.env.example`, `.python-version`, `.streamlit/config.toml`,
  `pyproject.toml`, `requirements.txt`.
- Added application: `app.py`, `tutortrace/__init__.py`, `errors.py`, `models.py`,
  `persistence.py`, ingestion `__init__.py` / `service.py` / `pdf.py` /
  `pdf_worker.py` / `pptx.py`, retrieval `__init__.py` / `chunking.py` / `search.py`,
  provider `__init__.py` / `llm.py`.
- Added tests: `tests/conftest.py`, `test_ingestion.py`, `test_retrieval.py`, `test_app.py`.
- Added fixtures/tools: `scripts/__init__.py`, `create_demo_assets.py`, `smoke_test.py`,
  `demo_assets/README.md`, `energy_notes.pdf`, `energy_slides.pptx`.
- Added documentation: `docs/ARCHITECTURE.md`, `KNOWN_LIMITATIONS.md`,
  `AI_DISCLOSURE.md`, this verification report.
- Newly tracked, unchanged supplied planning documents:
  `TutorTrace_AI_Coding_Agent_Prompt.md`, `docs/TutorTrace_AI_First_Place_Blueprint.md`.

## Git and Claude Code review

The implementation diff was inspected, and the staged implementation whitespace
check used:

```powershell
git diff --cached --check -- . ':!docs/TutorTrace_AI_First_Place_Blueprint.md'
```

The supplied blueprint contains intentional Markdown two-space hard line breaks;
it was preserved rather than rewritten merely to satisfy that whitespace check.
The small generated PDF was initially classified by Git as text. Binary attributes
for PDF/PPTX files now prevent line-ending conversion on checkout. Both staged
sample blobs were compared byte-for-byte with their working files before commit.
Ignore rules were tested for private uploads under `data/`, databases and journals,
environment files, Streamlit secrets and credential files. Common credential
patterns were scanned by filename only; none were found. No local database, private
upload, environment or package cache is part of the commit.

**Ready for independent Claude Code review; that review has not been performed.**
Re-run the commands above, then examine transaction boundaries, exact citation
resolution, blank-unit handling, literal search terms, subprocess error handling,
and upload failure/duplicate behavior. Review `KNOWN_LIMITATIONS.md` before planning
the next milestone. No unresolved defect was observed in the executed checks;
the documented scope limits still apply. This is a verified foundation, not a claim
that the full multimodal/adaptive-tutoring product or hackathon gates are complete.
