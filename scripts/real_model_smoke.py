"""Explicit real-model integration test; no mocks, skips or automatic downloads."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import tempfile

from tutortrace.ingestion.service import ingest
from tutortrace.persistence import Store
from tutortrace.providers.adapters import OllamaEmbedder, make_provider
from tutortrace.retrieval.context import retrieve_context
from tutortrace.tutoring import ask

ROOT = Path(__file__).resolve().parents[1]


def run(hybrid=False):
    provider = make_provider()
    embedder = OllamaEmbedder() if hybrid else None
    with tempfile.TemporaryDirectory(prefix="real-model-smoke-", dir=ROOT / "data") as folder:
        store = Store(Path(folder) / "sources.sqlite3")
        for name in ("energy_notes.pdf", "energy_slides.pptx"):
            ingest(store, name, (ROOT / "demo_assets" / name).read_bytes())
        result = ask(store, "How is kinetic energy calculated?", provider, embedder=embedder)
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2), flush=True)
        assert result.inference_succeeded and result.status == "answered", result.message
        if hybrid:
            assert result.context.mode == "hybrid" and not result.context.warnings, result.context.warnings
        citations = [support for claim in result.claims for support in claim.supports]
        assert citations
        assert any(support.evidence.filename == "energy_notes.pdf" and support.evidence.location == 1 for support in citations)
        reopened = Store(store.path)
        for support in citations:
            assert reopened.resolve_evidence(support.evidence.chunk_id) == support.evidence
            assert support.quote in support.evidence.text
        empty = ask(reopened, "zygomorphic xenoglossia", provider)
        assert empty.status == "abstained" and not empty.inference_succeeded
        if hybrid:
            question = "Which quantity represents how quickly a job gets done?"
            lexical = retrieve_context(store, question)
            semantic = retrieve_context(store, question, embedder=embedder)
            print(json.dumps({"semantic_probe_question":question,
                              "keyword_sources":[e.citation for e in lexical.evidence],
                              "hybrid_sources":[e.citation for e in semantic.evidence],
                              "mode":semantic.mode,"warnings":semantic.warnings}), flush=True)
        print("REAL MODEL SMOKE PASS: generated answer, exact source quotes, canonical PDF citation, restart and empty-retrieval abstention.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hybrid", action="store_true")
    run(parser.parse_args().hybrid)
