# AI assistance and attribution

Milestone 1 code, tests, sample educational text, documentation and local verification
were produced with OpenAI Codex assistance under the developer's instructions.
No code or assets were copied from unrelated private repositories. The supplied
project blueprint and coding prompt were read as planning context.

Milestone 2 adds actual local Ollama inference, optional local embeddings, a
credential-configured remote adapter, and a source-grounded tutoring pipeline.
Its implementation, synthetic evaluation cases, tests and documentation were
also produced with Codex assistance. Deterministic test doubles are used only
in tests; the application never replaces failed inference with mocked answers.
No visual understanding or measured learning improvements are claimed.

Original educational fixtures are described in `demo_assets/README.md` and dedicated
to CC0. Third-party software is installed as dependencies, not vendored:

- Streamlit — UI and application test harness.
- PyMuPDF — PDF extraction, sample generation and page rendering; AGPL/commercial terms.
- python-pptx — PowerPoint extraction and original sample generation.
- pytest — automated testing.
- SQLite / Python standard library — persistent source ledger and FTS5 retrieval.
- Ollama — separately installed local inference service; no model files are vendored.
- Qwen3 4B and nomic-embed-text — preexisting local models used for actual inference
  and embedding verification. Their upstream model licenses apply independently.

The educational text in `evaluation/cases.json` is self-authored for this project
and dedicated to CC0. It includes deliberately contradictory facts and instruction
injection examples for testing; those are not teaching claims or benchmark results.

Transitive dependency versions are recorded in `requirements.txt`; each dependency
retains its own license. The project owner should choose the repository license
and review third-party obligations before public distribution.

Claude Code's independent audit has not been performed as part of this milestone.
Readiness for review does not imply independent approval or hackathon acceptance.
