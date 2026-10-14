"""Reproducible diagnostic evaluation. Model mode makes real inference calls."""

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import tempfile
import time

from scripts.create_demo_assets import make_pdf, make_pptx
from tutortrace.ingestion.service import ingest
from tutortrace.persistence import Store
from tutortrace.providers.adapters import OllamaEmbedder, make_provider
from tutortrace.retrieval.context import ContextConfig, retrieve_context
from tutortrace.tutoring import ask, build_request, validate_answer
from tutortrace.providers.llm import InvalidAnswer

ROOT = Path(__file__).resolve().parents[1]


class RecordingProvider:
    """Record raw outputs only for this synthetic, explicitly public evaluation."""
    def __init__(self, provider):
        self.provider = provider
        self.config = provider.config
        self.last_completion = None

    def complete(self, messages, schema):
        self.last_completion = self.provider.complete(messages, schema)
        return self.last_completion


def citation_challenges(store, document_id):
    context = retrieve_context(store, "kinetic", document_ids=(document_id,))
    sources, _, _ = build_request("kinetic", context)
    evidence = sources["E1"]
    challenges = []
    for alias, quote in [("E999", evidence.text), ("E1", "This fabricated quotation is not in the source.")]:
        raw = json.dumps({"status":"answered", "claims":[{"text":"Challenge", "supports":[{"source_id":alias,"quote":quote}]}], "unsupported_aspects":[]})
        try:
            validate_answer(store, raw, sources)
            rejected = False
        except InvalidAnswer:
            rejected = True
        challenges.append({"challenge":"unknown source" if alias == "E999" else "fabricated excerpt", "rejected":rejected})
    return challenges


def run(output, *, real=False, hybrid=False, only=None):
    dataset = json.loads((ROOT / "evaluation/cases.json").read_text(encoding="utf-8"))
    provider = RecordingProvider(make_provider()) if real else None
    embedder = OllamaEmbedder() if hybrid else None
    settings = ContextConfig()
    results = []
    with tempfile.TemporaryDirectory(prefix="tutor-evaluation-", dir=ROOT / "data") as folder:
        store = Store(Path(folder) / "sources.sqlite3")
        ids = {}
        for source in dataset["documents"]:
            data = make_pdf(tuple(source["units"])) if source["filename"].endswith(".pdf") else make_pptx(tuple(source["units"]))
            ids[source["filename"]] = ingest(store, source["filename"], data).document.id
        challenges = citation_challenges(store, ids["fundamentals.pdf"])
        for case in dataset["questions"]:
            if only and case["id"] not in only:
                continue
            scope = tuple(ids[name] for name in case["scope"])
            start = time.perf_counter()
            if real:
                provider.last_completion = None
                result = ask(store, case["question"], provider, document_ids=scope, config=settings, embedder=embedder)
                context = result.context
            else:
                context = retrieve_context(store, case["question"], document_ids=scope, config=settings, embedder=embedder)
            selected = {(e.filename, e.location) for e in context.evidence}
            expected = {tuple(pair) for pair in case["expected_sources"]}
            row = {"id":case["id"], "category":case["category"], "question":case["question"],
                   "expected_sources":case["expected_sources"], "selected_sources":sorted(selected),
                   "retrieval_all_expected": expected.issubset(selected) if expected else None,
                   "expected_hits":len(expected & selected), "expected_count":len(expected),
                   "selected_count":len(selected), "retrieval_mode":context.mode, "warnings":context.warnings,
                   "elapsed_seconds":round(time.perf_counter()-start, 3)}
            if real:
                cited = [support for claim in result.claims for support in claim.supports]
                supplied_ids = {e.chunk_id for e in context.evidence}
                valid = sum(s.evidence.chunk_id in supplied_ids and s.quote in s.evidence.text for s in cited)
                text = " ".join(c.text for c in result.claims).casefold()
                row.update({"status":result.status, "status_expected":result.status in case["expected_status"],
                            "inference_succeeded":result.inference_succeeded, "citation_count":len(cited), "valid_citations":valid,
                            "raw_completion":provider.last_completion.content if provider.last_completion else None,
                            "expected_term_check":all(term.casefold() in text for term in case["expected_terms"]) if case["expected_terms"] else None,
                            "result":asdict(result)})
            results.append(row)
            print(json.dumps({key:value for key,value in row.items() if key != "result"}), flush=True)
            # Keep completed observations even if a later request or the session is interrupted.
            write_report(output, results, challenges, provider, hybrid, settings)
    return write_report(output, results, challenges, provider, hybrid, settings)


def write_report(output, rows, challenges, provider, hybrid, settings):
    labelled = [row for row in rows if row["expected_count"]]
    unsupported = [row for row in rows if row["category"] == "unsupported"]
    latencies = [row["elapsed_seconds"] for row in rows]
    summary = {"questions_run":len(rows),
               "retrieval_all_expected":{"numerator":sum(row["retrieval_all_expected"] for row in labelled),"denominator":len(labelled)},
               "source_recall":{"numerator":sum(row["expected_hits"] for row in labelled),"denominator":sum(row["expected_count"] for row in labelled)},
               "selected_source_precision":{"numerator":sum(row["expected_hits"] for row in labelled),"denominator":sum(row["selected_count"] for row in labelled)},
               "injected_citations_rejected":{"numerator":sum(c["rejected"] for c in challenges),"denominator":len(challenges)},
               "latency_seconds":{"median":statistics.median(latencies) if latencies else None,"max":max(latencies) if latencies else None}}
    if provider:
        summary.update({"inference_completed":sum(row["inference_succeeded"] for row in rows),
                        "errors":sum(row["status"] == "error" for row in rows),
                        "citation_validity":{"numerator":sum(row["valid_citations"] for row in rows),"denominator":sum(row["citation_count"] for row in rows)},
                        "unsupported_abstention":{"numerator":sum(row["status"] == "abstained" for row in unsupported),"denominator":len(unsupported)},
                        "expected_status":{"numerator":sum(row["status_expected"] for row in rows),"denominator":len(rows)}})
    config = None if provider is None else {"provider":provider.config.provider, "model":provider.config.model,
              "timeout":provider.config.timeout,"context_tokens":provider.config.context_tokens,
              "output_tokens":provider.config.output_tokens,"temperature":0,"seed":17 if provider.config.provider == "ollama" else None}
    report = {"recorded_at_utc":datetime.now(timezone.utc).isoformat(), "mode":"real-inference" if provider else "retrieval-only",
              "provider_configuration":config, "hybrid_requested":hybrid, "context_configuration":asdict(settings),
              "limitations":"Small self-authored diagnostic set, not an independent benchmark. Term checks and citation validity do not measure semantic faithfulness. Errors are not counted as successful abstentions. Latency includes retrieval and local model loading.",
              "summary":summary,"citation_challenges":challenges,"cases":rows}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real", action="store_true", help="Call the configured LLM; otherwise evaluate retrieval only")
    parser.add_argument("--hybrid", action="store_true", help="Use the installed local embedding model too")
    parser.add_argument("--only", nargs="+", help="Question IDs to run")
    parser.add_argument("--output", type=Path, default=ROOT / "data/m2-evaluation.json")
    args = parser.parse_args()
    result = run(args.output, real=args.real, hybrid=args.hybrid, only=args.only)
    print(json.dumps(result["summary"], indent=2))
