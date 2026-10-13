from dataclasses import replace
import json
import subprocess
import sys

import pytest

from tutortrace.errors import ProvenanceError, SearchQueryError, StorageError
from tutortrace.ingestion.service import ingest
from tutortrace.models import ExtractedUnit, digest, unit_identifier
from tutortrace.persistence import Store
from tutortrace.retrieval.chunking import CHUNK_SIZE, chunk_units
from tutortrace.retrieval.search import search


def test_search_finds_evidence_and_limits_scope(store, pdf_bytes, pptx_bytes):
    physics = ingest(store, "physics.pdf", pdf_bytes).document
    ingest(store, "biology.pptx", pptx_bytes)
    results = search(store, "What is kinetic energy?")
    assert "Kinetic" in results[0].text
    assert results[0].citation == "physics.pdf, page 1"
    assert len(search(store, "energy", limit=1)) == 1
    assert all(result.document_id == physics.id for result in search(store, "energy", document_id=physics.id))
    assert search(store, "photosynthesis", document_id=physics.id) == []
    assert search(store, "quantumchromodynamics") == []


@pytest.mark.parametrize("query", ["", "   ", "!!!", '" OR * NEAR(', "the is and", "'; DROP TABLE documents; --"])
def test_query_syntax_is_literal_and_safe(store, pdf_bytes, query):
    ingest(store, "source.pdf", pdf_bytes)
    assert search(store, query) == []
    assert len(store.list_documents()) == 1


@pytest.mark.parametrize("limit", [0, -1, 51, True, 2.5])
def test_invalid_search_limits(store, limit):
    with pytest.raises(SearchQueryError):
        search(store, "energy", limit=limit)


def test_query_length_limits(store):
    with pytest.raises(SearchQueryError):
        search(store, "x" * 1001)
    with pytest.raises(SearchQueryError):
        search(store, " ".join(f"term{number}" for number in range(65)))


def test_chunking_exact_offsets_no_cross_page_or_gaps():
    units = (ExtractedUnit(1, "alpha beta gamma " * 400), ExtractedUnit(2, ""), ExtractedUnit(3, "delta " * 300))
    document_id = digest(b"fixture")
    first = chunk_units(document_id, units)
    second = chunk_units(document_id, units)
    assert first == second
    assert len({chunk.id for chunk in first}) == len(first)
    for unit in (units[0], units[2]):
        unit_chunks = [chunk for chunk in first if chunk.unit_id == unit_identifier(document_id, unit.location)]
        coverage = set()
        for chunk in unit_chunks:
            assert chunk.text == unit.text[chunk.start:chunk.end]
            assert 0 < len(chunk.text) <= CHUNK_SIZE
            coverage.update(range(chunk.start, chunk.end))
        assert coverage == set(range(len(unit.text)))
    assert first[1].start < first[0].end


def test_unbroken_long_word_terminates_without_losing_text():
    chunks = chunk_units("document", (ExtractedUnit(1, "x" * 4000),))
    assert len(chunks) == 4
    assert chunks[-1].end == 4000
    assert all(chunk.end - chunk.start <= CHUNK_SIZE for chunk in chunks)


def test_deterministic_ids_across_independent_databases(store, tmp_path, pdf_bytes):
    other = Store(tmp_path / "other.sqlite3")
    for target in (store, other):
        ingest(target, "source.pdf", pdf_bytes)
    assert search(store, "energy") == search(other, "energy")


def test_persistence_in_fresh_python_process(store, pdf_bytes):
    result = ingest(store, "source.pdf", pdf_bytes)
    script = """
import json, sys
from tutortrace.persistence import Store
from tutortrace.retrieval.search import search
from tutortrace.models import digest
s = Store(sys.argv[1])
e = search(s, 'gravity')[0]
print(json.dumps({'citation': e.citation, 'document_id': digest(s.original(e.document_id)), 'attempts': len(s.recent_attempts())}))
"""
    completed = subprocess.run([sys.executable, "-c", script, str(store.path)], capture_output=True, text=True, check=True)
    payload = json.loads(completed.stdout)
    assert payload == {"citation": "source.pdf, page 3", "document_id": result.document.id, "attempts": 1}


def test_citation_is_resolved_from_ledger_not_caller_text(store, pdf_bytes):
    ingest(store, "source.pdf", pdf_bytes)
    found = search(store, "gravity")[0]
    caller_modified = replace(found, filename="invented.pdf", location=999, text="fabricated")
    resolved = store.resolve_evidence(caller_modified.chunk_id)
    assert resolved.citation == "source.pdf, page 3"
    assert "Gravity" in resolved.text
    with pytest.raises(ProvenanceError):
        store.resolve_evidence("invented-id")
    with pytest.raises(ProvenanceError):
        store.original("invented-id")


def test_tampered_passage_detected(store, pdf_bytes):
    ingest(store, "source.pdf", pdf_bytes)
    evidence = search(store, "gravity")[0]
    with store.connection() as db:
        db.execute("UPDATE chunks SET text = ? WHERE id = ?", ("Fabricated gravity evidence", evidence.chunk_id))
    with pytest.raises(ProvenanceError):
        store.resolve_evidence(evidence.chunk_id)
    with pytest.raises(ProvenanceError):
        search(store, "gravity")


def test_tampered_original_detected(store, pdf_bytes):
    document = ingest(store, "source.pdf", pdf_bytes).document
    with store.connection() as db:
        db.execute("UPDATE documents SET original = ? WHERE id = ?", (b"changed", document.id))
    with pytest.raises(ProvenanceError):
        store.original(document.id)


def test_failed_chunk_insert_rolls_back_original_units_and_fts(store, pdf_bytes):
    with store.connection() as db:
        db.execute("""CREATE TRIGGER fail_second BEFORE INSERT ON chunks WHEN new.text LIKE 'Gravity%'
                   BEGIN SELECT RAISE(ABORT, 'injected failure'); END""")
    with pytest.raises(StorageError):
        ingest(store, "source.pdf", pdf_bytes)
    with store.connection() as db:
        for table in ("documents", "units", "chunks", "ingestion_attempts"):
            assert db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
    assert search(store, "kinetic") == []


def test_future_schema_rejected(store):
    with store.connection() as db:
        db.execute("PRAGMA user_version = 999")
    with pytest.raises(StorageError, match="schema 999"):
        Store(store.path)


def test_corrupted_database_rejected(tmp_path):
    path = tmp_path / "corrupt.sqlite3"
    path.write_bytes(b"not a sqlite database")
    with pytest.raises(StorageError):
        Store(path)
