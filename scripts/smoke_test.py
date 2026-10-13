"""Real file ingestion, reopened database, exact evidence checks; no mocked outputs."""

from dataclasses import asdict
import json
from pathlib import Path
import tempfile

from tutortrace.ingestion.service import ingest
from tutortrace.persistence import Store
from tutortrace.retrieval.search import search

ROOT = Path(__file__).resolve().parents[1]


def main():
    (ROOT / "data").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="smoke-", dir=ROOT / "data") as directory:
        database = Path(directory) / "smoke.sqlite3"
        store = Store(database)
        for filename in ("energy_notes.pdf", "energy_slides.pptx"):
            data = (ROOT / "demo_assets" / filename).read_bytes()
            result = ingest(store, filename, data)
            assert result.document.status == "indexed"
            assert store.original(result.document.id) == data
            print(json.dumps({"ingestion": asdict(result)}, indent=2))
            assert ingest(store, filename, data).duplicate
        reopened = Store(database)
        assert len(reopened.list_documents()) == 2
        for query, filename, location in (
            ("kinetic", "energy_notes.pdf", 1),
            ("gravitational", "energy_notes.pdf", 2),
            ("isolated", "energy_slides.pptx", 1),
            ("watts", "energy_slides.pptx", 2),
        ):
            evidence = search(reopened, query)[0]
            assert (evidence.filename, evidence.location) == (filename, location)
            assert evidence.text == evidence.unit_text[evidence.start:evidence.end]
            assert reopened.resolve_evidence(evidence.chunk_id).text == evidence.text
            print(json.dumps({"query": query, "citation": evidence.citation, "chunk_id": evidence.chunk_id, "passage": evidence.text}))
        assert search(reopened, "photosynthesis") == []
        print("SMOKE PASS: 2 originals, 2 duplicate checks, 4 exact source locations, persistence and no-match search verified.")


if __name__ == "__main__":
    main()
