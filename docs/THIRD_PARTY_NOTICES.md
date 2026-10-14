# Credits and license status

Release review: 14 October 2026. This is an attribution inventory, not a legal
compliance certification. Dependencies and model weights are not vendored.

## Project and assets

TutorTrace AI is developed by Akhilesh Selvan with OpenAI Codex assistance.
**There is no repository-wide code LICENSE file.** Public GitHub visibility is
not an open-source license grant. This documentation does not choose or grant a
new code license on the owner's behalf. The owner must resolve intended licensing
and applicable third-party distribution obligations.

The original demo text/generated PDF/PPTX and explicitly identified synthetic
evaluation fixtures are dedicated to [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/),
as recorded in [demo provenance](../demo_assets/README.md) and
[AI disclosure](AI_DISCLOSURE.md). This dedication does not cover application
code, dependencies or model weights. No unrelated private repository or private
educational material was used in the submitted fixtures.

## Main dependencies and models

| Component | Role | License / upstream reference |
|---|---|---|
| Python | Runtime and standard library | [PSF license documentation](https://docs.python.org/3/license.html) |
| SQLite | Source and learner storage, FTS5 | [Public-domain statement](https://sqlite.org/copyright.html) |
| Streamlit 1.65.0 | Interface and AppTest | Apache-2.0, installed metadata; [upstream](https://github.com/streamlit/streamlit/blob/develop/LICENSE) |
| PyMuPDF 1.28.2 / MuPDF | PDF extraction/rendering | GNU AGPL 3.0 or Artifex commercial terms; [official licensing](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright) |
| python-pptx 1.0.2 | PPTX extraction and sample authoring | MIT, installed metadata; [upstream](https://github.com/scanny/python-pptx/blob/master/LICENSE) |
| pytest 9.1.1 | Tests | MIT, installed metadata; [upstream](https://github.com/pytest-dev/pytest/blob/main/LICENSE) |
| Ollama | Separately installed inference service | [Upstream license](https://github.com/ollama/ollama/blob/main/LICENSE) |
| Qwen3 4B | Separately installed generation model | [Model license](https://huggingface.co/Qwen/Qwen3-4B/blob/main/LICENSE) |
| nomic-embed-text | Optional separately installed embeddings | [Model repository/license information](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5) |

`requirements.txt` pins the verified environment, including transitive packages.
Each installed distribution retains its own license and notices; the table is not
a replacement for all transitive license texts. No commercial PyMuPDF license is
claimed. Review the actual intended use and distribution against applicable terms.
No paid API access or rights to third-party course content are granted by this project.
