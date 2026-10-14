"""Actual ingestion → assessment → grading → revision → fresh-process restart.

Optional --real-model invokes the configured provider once; failures are recorded
and produce a nonzero exit, never substituted answers. All data is self-authored.
"""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time

from tutortrace.assessment import verify_question
from tutortrace.ingestion.pdf import render_pdf_page
from tutortrace.ingestion.service import ingest
from tutortrace.learning import LearningStore, recommendations, revision_request
from tutortrace.persistence import Store
from tutortrace.providers.adapters import make_provider
from tutortrace.providers.llm import ProviderConfig
from tutortrace.retrieval.context import ContextConfig
from tutortrace.tutoring import ask

ROOT = Path(__file__).resolve().parents[1]


def run(directory, real_model=False):
    started = time.perf_counter()
    source = Store(directory / "source.sqlite3")
    learning = LearningStore(directory / "source.learning.sqlite3")
    documents = [ingest(source, name, (ROOT / "demo_assets" / name).read_bytes()).document
                 for name in ("energy_notes.pdf", "energy_slides.pptx")]
    learner = learning.create_learner("Milestone 3 smoke learner")
    sid = learning.begin(source, learner, "energy", count=3)
    session = learning.session(learner, sid)
    assert {q.kind for q in session["questions"]} == {"mcq", "short", "numerical"}
    responses = {q.id: (next(option for option in q.options if option != q.answer) if q.kind == "mcq" else q.answer)
                 for q in session["questions"]}
    graded = learning.submit(source, learner, sid, responses)
    assert [row["status"] for row in graded["attempts"]] == ["incorrect", "correct", "correct"]
    dashboard = learning.dashboard(learner)
    assert dashboard[0]["score"] == 0.6
    recs = recommendations(source, learning, learner)
    assert recs and recs[0]["evidence"]
    citations = []
    previewed = False
    for question in session["questions"]:
        item = verify_question(source, question)
        citations.append(item.citation)
        if item.source_type == "pdf" and not previewed:
            preview = render_pdf_page(source.original(item.document_id), item.location)
            assert preview.startswith(b"\x89PNG")
            previewed = True
    assert previewed and any("slide" in citation for citation in citations)
    # A separate interpreter reopens both databases, matching a genuine restart.
    code = """import json,sys
from tutortrace.learning import LearningStore
from tutortrace.persistence import Store
l=LearningStore(sys.argv[1]); s=Store(sys.argv[2]); u=sys.argv[3]
print(json.dumps({'dashboard':l.dashboard(u),'history_count':len(l.history(u)),'documents':len(s.list_documents())}))
"""
    child = subprocess.run([sys.executable, "-c", code, str(learning.path), str(source.path), learner],
                           cwd=ROOT, capture_output=True, text=True, timeout=30, check=True)
    reopened = json.loads(child.stdout)
    assert reopened["dashboard"] == dashboard and reopened["history_count"] == 3 and reopened["documents"] == 2
    question, scopes = revision_request(recs[0])
    report = {"documents": [{"name": doc.filename, "id": doc.id} for doc in documents],
              "formats": [q.kind for q in session["questions"]], "citations": citations,
              "grades": [{"status": row["status"], "score": row["score"], "mastery_after": row["mastery_after"]} for row in graded["attempts"]],
              "mastery": dashboard[0]["score"], "next_difficulty": dashboard[0]["next_difficulty"],
              "revision_reason": recs[0]["reason"], "revision_question": question,
              "pdf_preview_verified": previewed, "fresh_process_restart_verified": True,
              "real_inference_requested": real_model}
    if real_model:
        defaults = ProviderConfig.from_env()
        # One bounded request with a smaller context/output allowance. No model downloads.
        config = ProviderConfig(provider=defaults.provider, model=defaults.model, base_url=defaults.base_url,
                                api_key=defaults.api_key, timeout=120, context_tokens=2048, output_tokens=500)
        result = ask(source, question, make_provider(config), document_ids=scopes,
                     config=ContextConfig(max_passages=2, max_characters=1800))
        report["real_inference"] = asdict(result)
        report["provider_configuration"] = {"provider": config.provider, "model": config.model,
                                             "timeout": config.timeout, "context_tokens": config.context_tokens,
                                             "output_tokens": config.output_tokens}
    report["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--real-model", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/evaluation/m3-smoke.json")
    args = parser.parse_args()
    (ROOT / "data").mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="learning-smoke-", dir=ROOT / "data") as folder:
        report = run(Path(folder), args.real_model)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "real_inference"}, indent=2))
    if args.real_model:
        result = report["real_inference"]
        print(f"Real inference: {result['status']} / succeeded={result['inference_succeeded']} / {result['elapsed_seconds']:.2f}s")
        if not result["inference_succeeded"] or result["status"] not in ("answered", "conflict"):
            raise SystemExit(1)


if __name__ == "__main__":
    main()
