# TutorTrace AI — First-Place Attempt Blueprint
**Event:** Multimodal AI Hackathon 2026, IIT Mandi / KamandPrompt and partners  
**Track:** D — Personalized Tutoring & Adaptive Learning  
**Team:** Solo  
**Deadline:** 15 October 2026, 00:15 IST  
**Target:** Compete for Track D first prize (₹15,000). Winning is not guaranteed.

## 1. Winning product thesis
**TutorTrace AI** is a **citation-to-mastery** learning system: a learner uploads a lecture video, a chapter PDF, and slides; receives answers with **click-through exact page / slide / timestamp evidence**, takes a verified quiz, gets diagnosed on misconceptions, and sees mastery levels change across sessions. Demonstrate the *complete feedback loop*, not a chatbot with a quiz button.

Signature demo: Ask a question whose answer depends on a **diagram in a slide**; jump to the precise slide; ask an out-of-syllabus question and see a refusal; answer a quiz item incorrectly; get source-cited remediation; retest; show the topic-level mastery trajectory changing and a revision recommendation.

## 2. Official rubric mapped to build priorities
| Criterion | Weight | Judge-visible proof |
|---|---:|---|
| Knowledge Base & Grounding | 20% | Video/PDF/PPTX upload; diagrams; working PDF-page/PPT-slide/video-timestamp navigation; correct citations and abstention. |
| Personalization Effectiveness | 20% | Persisted per-topic mastery; cold-start diagnostic; 3-session weak/strong simulated-student evaluation; evolving recommendations. |
| Assessment Quality | 15% | Verified MCQ + short-answer + numerical items; topic/source/difficulty tags; non-repeat logic; grounded answer feedback. |
| User Experience & Demo | 15% | Fast, clear ingestion→ask→quiz→mastery flow with sample course preloaded. |
| System Evaluation | 15% | Team-built test set; framework-based faithfulness/relevancy/context precision/recall where genuinely run; abstention rate; mastery trend; repetition rate. |
| Technical Implementation | 15% | Tested, reproducible pipeline; deterministic data models; CI or local test logs; error handling; documented limitations. |

**The most important differentiator is traceability through the full learning loop**: every content unit, generated question, answer, diagnosis and recommendation can be tied to an uploaded source.

## 3. Minimum demo scope (do all, avoid shallow bonus features)
1. **Three modalities:** PDF textbooks, PPTX slides, MP4 lecture audio/video. Transcribe speech with timestamps; sample and inspect slide/keyframes where possible; parse embedded PDF/PPTX diagrams/images, using an available vision-capable provider; clearly flag unprocessed visuals.
2. **Source ledger:** `source_id`, `source_type`, `unit_id`, `topic_id`, `page_number | slide_number | start_seconds/end_seconds`, `extracted_text`, `visual_description`, `processing_status`. Never fabricate coordinates or timestamps.
3. **Retrieval and chat:** topic-aware hybrid retrieval, citation-backed answer, click-through sources; refuse out-of-material requests or visibly separate non-source knowledge.
4. **Assessments:** MCQs, short answers and numerical questions at selectable topic/difficulty, with answer keys checked against source evidence; non-repeat registry. MCQ auto-grade; numerical via safe symbolic/numeric checking; short-answer with rubric/evidence and flagged uncertainty.
5. **Learner model:** persisted topic mastery using a documented BKT-style update (initial mastery, guess, slip, learning transition) after each assessment; cold start via diagnostic; explicit rule for chat-only interactions so mastery does not change from unverified chat answers.
6. **Evaluation:** A small, public/course-owned test corpus with at least 24 sourced questions across modalities, 8 out-of-material questions, 4 figure/diagram questions; test citation match/abstentions. Run a recognized framework (RAGAS/DeepEval/TruLens or similar) on a verifiable subset and report *actual* measured values, not invented scores. Simulate at least two learner profiles over three sessions; record mastery estimate trends and repeated-question rate.
7. **Product:** one-page dashboard with upload status, citations, chat, assessment, mastery and evaluation results; friendly sample-data path without paid services.

## 4. Practical solo tech stack
- **Rapid prototype UI:** Streamlit (with clean multipage/panel structure, custom CSS only where needed, and Plotly for learner analytics).
- **Language:** Python 3.11; Pydantic models and SQLite for durable state; pytest.
- **Ingestion:** PyMuPDF, python-pptx, FFmpeg / faster-whisper (CPU), OpenCV frame sampling where feasible. Optical image/diagram understanding through a vision-capable provider adapter, with explicit failure status if unavailable.
- **Search:** SQLite FTS5 plus cached embeddings (local lightweight sentence-transformers/nomic as supported); deterministic references to source units.
- **Generation:** provider adapter supporting a free/local configured LLM. Never depend on an unverified API key, model quota or GPU. Do not fake generated results to make the demo work.
- **Evaluation:** deterministic provenance/abstention tests first; framework metrics on an actual saved benchmark run; record environment, seed, model and timestamps.

Keep extraction, evidence indexing, assessment grading, learner-state updates and report generation separate modules. Every output stores which source and model produced it. Integrations can fail gracefully rather than hanging the live demo.

## 5. Repo structure
```
tutortrace-ai/
  app.py
  tutortrace/
    models.py                 # canonical schemas and provenance
    ingestion/{pdf,pptx,video,visuals}.py
    retrieval/{index,search,grounding}.py
    assessment/{generate,verify,grade}.py
    mastery/{bkt,diagnostic}.py
    providers/{llm,vision}.py
    evaluation/{benchmark,sim_students}.py
    persistence.py
  demo_assets/                # legal, small, credited material
  tests/
  docs/{architecture,limitations,ai_disclosure}.md
  data/                       # ignored mutable local data
  requirements.txt
  README.md
  .env.example
  .gitignore
```

## 6. Time-boxed sprint (IST)
- **13 Oct, first 8 hours:** independent public repository + environment + demo assets; PDF/PPTX/video ingestion to source ledger; sample corpus indexed and provenance tested.
- **13 Oct, next 8 hours:** retrieval/chat with exact citations, working source navigation, out-of-material refusals; basic end-to-end tests.
- **13 Oct evening–14 Oct early:** generation/verification of 3 quiz types, deterministic grading, topic mastery persistence, diagnostic and weak-topic recommendation.
- **14 Oct daytime:** evaluation datasets, framework-based metrics, two learner simulations, tests and figures; diagram-path verification; reliability fixes.
- **14 Oct by 20:00:** code freeze; rehearse demo, record/upload 3–10-minute English YouTube video, prepare public GitHub README and Devpost materials.
- **14 Oct by 22:30:** final Devpost submission verified with screenshot, then mark 'Submission Done' on Unstop. Reserve ~105 minutes for upload, account and network failures.

## 7. Nonnegotiable acceptance gates
- **Gate A:** Three actual uploads populate the evidence ledger; PDF pages, slide numbers, and video timestamps survive the entire pipeline.
- **Gate B:** On a 10-question checked set, every displayed source link navigates to the exact relevant unit; missing supporting evidence → visible abstention.
- **Gate C:** Each of MCQ, short answer and numerical assessment types works with source/difficulty/topic labels; no repeated question IDs on a second quiz.
- **Gate D:** Mastery persists after restart, cold-start diagnostic works, weak-topic recommendations change only from graded evidence.
- **Gate E:** Automated tests pass, benchmark JSON exists, metrics are labeled measured vs not run, and simulated-student results are honestly labeled simulations.
- **Gate F:** Someone can install from README and reproduce an offline or documented free-tier demo; video and Devpost links open without permission requests.

## 8. Competition / ethics / intellectual property
- Do **not** copy code or private student/lesson data from the two-founder private `ai-tuition-app` into this public submission without the project's co-owner's permission. Use only original implementation or independently owned LocalPilot components under licenses/rights you control, disclosing preexisting reuse as appropriate.
- Declare AI coding tools in Devpost 'Built With' and README, specifying AI-assisted files/operations. Be able to explain every critical algorithm and output.
- Use only licensed/public-domain/self-created course materials, citing origins in README. No personally identifying student data.
- Do not claim measured learning gains from simulated profiles are evidence of improved human learning.
- Never claim unsupported source-grounding, multimodal understanding, or evaluation metrics.

## 9. Demo storyboard (target ~5 min; Track D permits 3–10 min)
1. 0:00–0:25: challenge and what differs from a chatbot.
2. 0:25–1:10: upload PDF, PPTX, MP4; show extraction, diagram and citations with precise locations.
3. 1:10–2:00: answer grounded question with live jump-to-source; show abstention on unrelated question.
4. 2:00–3:15: create varied verified quiz, wrong response, feedback, weak topic change; answer correctly on follow-up.
5. 3:15–4:10: mastery graph and 3-session simulated learners; discuss cautious interpretation.
6. 4:10–5:00: benchmark results, architecture, limitations, reproducibility and closing.

## 10. Devpost metadata draft
**Name:** TutorTrace AI  
**Tagline:** From every lecture, slide and diagram to cited answers, verified quizzes and measurable mastery.  
**Track:** D — Personalized Tutoring & Adaptive Learning (select "Track D" in the actual form).  
**Team:** solo; leader email: use your verified Devpost email.  
**Built With:** Python, Streamlit, PyMuPDF, python-pptx, faster-whisper, SQLite, [actual embedding/LLM/vision providers used], pytest, [AI coding assistants actually used].

### Final submission checklist
- [ ] Devpost project created, correctly associated with event and Track D
- [ ] Public GitHub, README, license/attributions, reproducible setup, test/evaluation instructions
- [ ] Video URL (YouTube public/unlisted, not private) 3–10 minutes, working system
- [ ] App demo link if reliable (optional)
- [ ] Real full name and verified leader email entered
- [ ] Devpost status **Submitted**, not Draft, confirmed with screenshot
- [ ] Only then mark Unstop **Submission Done**
