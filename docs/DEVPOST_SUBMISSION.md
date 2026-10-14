# TutorTrace AI — Devpost submission draft

**Prepared for manual entry only. Nothing has been submitted to Devpost.**
Track D — Personalized Tutoring & Adaptive Learning, Multimodal AI Hackathon 2026.
Event eligibility, exact form requirements and any video requirement must be
checked by the entrant; this draft does not certify compliance or acceptance.

## Project name

TutorTrace AI

## Tagline

Study your own materials with inspectable AI citations, source-verified practice,
and transparent revision priorities.

## Inspiration

Students studying chapters and slides need to know where an explanation came
from and what to revise next. Fluent AI output and unexplained mastery scores
can hide mistakes. We built a local workflow that keeps the original material
accessible and makes the evidence, grading rules and learner estimates visible.

## What it does

TutorTrace preserves uploaded PDF and PowerPoint files, extracts text by physical
page or slide, and provides searchable evidence with source previews/downloads.
A real AI tutor answers using selected passages, validates source references and
exact supporting quotes, and displays abstention or errors when appropriate.

Students create a local profile and complete source-derived diagnostic quizzes:
multiple choice, exact-wording short answers and numerical value recall. Every
key is reconstructed from its source instead of trusting a generated answer key.
Attempts persist across restarts. A transparent recall estimate prioritizes
weaker tracked topics, adjusts practice scaffolding, and prepares source-scoped
revision questions for the AI tutor.

PDF and PPTX are supported document formats, but this release reasons over their
extracted text. It does not implement video, OCR or visual diagram understanding.

## How we built it

Python 3.11 and Streamlit provide the interface. PyMuPDF and python-pptx extract
page/slide text. SQLite stores original files, source units and FTS5 search data;
a separate SQLite database stores learners, questions, sessions and grades.
Deterministic identifiers and transactional updates preserve provenance and
history. The provider-independent tutor uses local Ollama Qwen3 4B; a configurable
OpenAI-compatible remote adapter is also implemented but only contract-tested.
Optional local embeddings complement keyword retrieval.

The learner estimate is `(1 + correct) / (2 + correct + incorrect)`. It starts
at 50% meaning unknown; unverified short-answer wording does not change it.
It is an uncalibrated recall count model, not proof of mastery or a learning gain.

## Challenges

The main engineering challenges were preserving source identity across extraction
upgrades, rejecting invented citations without pretending to prove semantic
correctness, and making learner updates atomic. Limited local memory and CPU
inference also required bounded model requests and model-free grading.

## Accomplishments and verification

- Fresh release run: **216 automated tests passed**, zero failures/skips.
- Executed ingestion, exact page/slide citation, quiz/grading and separate-process
  persistence smoke checks, plus fresh Streamlit startup.
- One fresh real Qwen3 4B revision answered in **70.54 seconds**, with three
  accepted claims and three provenance/quote-validated support references.
- Earlier 13-case self-authored tutor diagnostic recovered 14/14 labelled source
  units, with keyword selected-source precision 14/21. These are small-set
  observations, not general semantic accuracy scores.
- Three simulated learner profiles completed **27/27 sessions and 81/81 answers**
  with zero repeated facts in the recorded run and 3/3 restart checks. Their answer
  patterns were prescribed; this is not evidence of real-student learning gains.

## What we learned

Reliable educational assistance needs explicit boundaries. Exact citations make
answers auditable but cannot prove reasoning correct. A small, understandable
learner model is easier to inspect than an unsupported claim of precise mastery.
Deterministic recall practice keeps the full learning loop usable even when a
local model is slow or unavailable.

## Limitations and next steps

Practice currently tests source recall, not broad conceptual understanding or
novel arithmetic. Paraphrased short answers require review; no semantic grading
or teacher adjudication interface exists. Difficulty and mastery are uncalibrated.
Profiles have no authentication, and local inference latency varies. Future work
would require teacher-reviewed assessment quality and real learner evaluation
before claiming educational impact. Video, OCR and diagram reasoning remain
unimplemented. Milestone 4 was not implemented in this release.

## Built with

Python 3.11, Streamlit, SQLite FTS5, PyMuPDF, python-pptx, Ollama, Qwen3 4B,
optional nomic-embed-text, pytest, Git.

## Team, AI assistance and data

Solo developer: Akhilesh Selvan. OpenAI Codex assisted implementation, tests,
self-authored synthetic fixtures and documentation. Real runtime answers use the
configured inference provider; mocks appear only in deterministic tests. No
independent Claude Code audit is claimed. Demo materials contain no private
educational documents or student data. See the AI disclosure and license notices.

## Links and manual submission checklist

- Repository: https://github.com/AkhileshSelvan/tutortrace-ai
- Setup: [README](../README.md)
- [Architecture](FINAL_ARCHITECTURE.md) · [Evaluation](FINAL_EVALUATION.md)
- [Demo script](DEMO_SCRIPT.md) · [AI disclosure](AI_DISCLOSURE.md)
- [Third-party and code-license status](THIRD_PARTY_NOTICES.md)
- Demo video: **not recorded or uploaded by this release task**; add an actual
  recording link if required by the event. No hosted deployment URL is claimed.
- Code license: **not selected**; the owner must resolve the intended license
  and third-party distribution obligations. Do not describe the code as licensed
  open source merely because the repository is public.
- Verify event rules, required fields, eligibility and deadline before submitting.
