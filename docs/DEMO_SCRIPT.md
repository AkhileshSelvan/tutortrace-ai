# TutorTrace AI — reproducible judging demo

Allow approximately 5 minutes plus local inference time. Show only self-authored
`demo_assets/energy_notes.pdf` (two pages) and `energy_slides.pptx` (two slides).
No private course material or student records are needed. The assets are committed;
regenerating them is unnecessary and may change byte-based document IDs.

## Prepare

Follow the Python 3.11 installation in the [README](../README.md). Check
`ollama list` for `qwen3:4b` and ensure the service is running. Do not download a
model during the demo. Use keyword retrieval to avoid embedding startup time.
Launch in a fresh, uniquely named data directory to avoid earlier quiz history:

```powershell
cd D:\tutortrace-ai
$env:TUTORTRACE_DATA_DIR = "D:\tutortrace-ai\data\demo-$(Get-Date -Format yyyyMMdd-HHmmss)"
$env:TUTORTRACE_LLM_PROVIDER = 'ollama'
$env:TUTORTRACE_LLM_MODEL = 'qwen3:4b'
$env:TUTORTRACE_LLM_URL = 'http://127.0.0.1:11434'
$env:TUTORTRACE_TIMEOUT = '120'
$env:TUTORTRACE_CONTEXT_TOKENS = '2048'
$env:TUTORTRACE_OUTPUT_TOKENS = '500'
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open http://127.0.0.1:8501. If occupied, use `--server.port 8502` and the matching
URL. Keep the same shell/data-directory value for a restart; do not rerun the
timestamp assignment when proving persistence. No deletion/reset is required.

## Walkthrough and narration

1. **Open and ingest.** Open the sidebar if collapsed. Click **Load sample course**,
   or choose both committed files and click **Ingest documents**. The library
   shows two documents, each with two units and two passages. Say: “Original bytes
   are preserved; this prototype extracts text, not diagrams or scans.”
2. **Search evidence.** Search `kinetic`. Show `energy_notes.pdf, page 1`, the
   passage and **Inspect citation and full source text** details. Use **Preview original page**.
   Search `isolated` to show `energy_slides.pptx, slide 1`. PPTX original downloads
   are supported; automatic navigation inside PowerPoint is not.
3. **Ask the AI tutor.** Scroll below Adaptive practice. Click **Check model status**.
   Keep semantic retrieval off. In Evidence limits choose two passages and 1,800
   source characters. Ask: `How is kinetic energy calculated?` Leave scope empty
   to use the two sample documents. Click **Ask AI tutor** and allow up to two
   minutes. Actual wording and latency may vary; do not promise a fixed response.
4. **Inspect citations.** Expand **Source for statement…** and **Inspect selected
   evidence and original sources**. Open the cited PDF page. Say: “These checks
   establish which source and exact quote were used, not that every generated
   claim is logically correct.” An error must remain visibly an error.
5. **Generate a diagnostic.** In Adaptive practice create `Demo learner`. Keep topic
   `energy`, empty course selection, `adaptive`, all three formats, three questions.
   Click **Generate assessment**. Say: “Keys come from deterministic source blanks;
   the model does not invent or grade them.”
6. **Complete the quiz.** For this exact initial sample/course, the first MCQ asks
   about constant total energy. Intentionally choose `between` (incorrect), enter
   `forms` for the short blank and `9` for the numerical blank. Read the displayed
   prompts first: if source bytes, selection or prior history differ, use the
   matching source answers instead. This is a scripted demonstration, not an
   independent student evaluation.
7. **Grade and inspect.** Click **Grade assessment**. Expected initial script:
   two matched, one did not match, zero needing review. Expand answers to show
   keys, excerpts and physical source citations. Different short wording is
   **needs review**, not automatically wrong. Numerical grading compares values.
8. **Show progress.** Dashboard: `energy`, 60%, two correct, one incorrect,
   next level `medium`. Explain `(1+2)/(2+2+1)=3/5`. Initial 50% means unknown;
   this is a recall estimate, not calibrated understanding. Expand the history
   chart: 1/3 → .5 → .6.
9. **Personalize revision.** Show Revision priorities and its denominator/reason.
   Expand source-backed revision. “No explicit prerequisite” is an honest state.
   Click **Revise with AI tutor** and show the prepared topic/level and selected
   documents. This prepares a request; **Ask AI tutor** performs a new inference.
   Avoid a second slow call if time is limited; the earlier live answer demonstrates
   inference, while this step demonstrates the personalized handoff.
10. **Persist.** Reload and select the same learner; grades remain. If practical,
    stop only your own foreground demo with Ctrl+C and rerun the same Streamlit
    command in the same shell. The same data directory restores the learner,
    assessment review and score. A reload alone is not a process restart.

## Reliable fallback and evidence

If AI fails or times out, show the explicit error and source passages, then continue
the deterministic quiz. Do not label retrieved text as an AI answer, substitute a
fake response, or present a previous recording as live. The committed
[release inference record](evaluation/release-real-smoke.json) may be shown as
**previously recorded verification** with its timing and configuration.

The following command automates ingestion, mixed quiz, grading, revision evidence,
PDF preview and a real separate-process persistence check in temporary local data:

```powershell
.\.venv\Scripts\python.exe -m scripts.learning_smoke --output data\demo-smoke.json
```

Append `--real-model` only when intentionally testing a live provider. The existing
[dashboard screenshot](evaluation/m3-dashboard.jpg) is an actual M3 browser capture,
not a generated UI or video. No submission video has been created in this release.
