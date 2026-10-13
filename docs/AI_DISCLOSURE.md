# AI assistance and attribution

Milestone 1 code, tests, sample educational text, documentation and local verification
were produced with OpenAI Codex assistance under the developer's instructions.
No code or assets were copied from unrelated private repositories. The supplied
project blueprint and coding prompt were read as planning context.

The application does **not** call an AI model. It extracts text and retrieves literal
evidence. AI-assisted development must not be described as runtime visual or tutoring
intelligence. The `AnswerProvider` protocol is a future integration contract only.

Original educational fixtures are described in `demo_assets/README.md` and dedicated
to CC0. Third-party software is installed as dependencies, not vendored:

- Streamlit — UI and application test harness.
- PyMuPDF — PDF extraction, sample generation and page rendering; AGPL/commercial terms.
- python-pptx — PowerPoint extraction and original sample generation.
- pytest — automated testing.
- SQLite / Python standard library — persistent source ledger and FTS5 retrieval.

Transitive dependency versions are recorded in `requirements.txt`; each dependency
retains its own license. The project owner should choose the repository license
and review third-party obligations before public distribution.

Claude Code's independent audit has not been performed as part of this milestone.
Readiness for review does not imply independent approval or hackathon acceptance.
