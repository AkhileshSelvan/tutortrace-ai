"""Milestone 1 audit regressions, including actual schema-v1 upgrade paths."""

from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from pathlib import Path
import sqlite3
import json
import subprocess
import sys

import pymupdf
import pytest

from scripts.create_demo_assets import make_pdf, make_pptx
from tutortrace import models, persistence
from tutortrace.errors import InvalidDocumentError, ProvenanceError, StorageError
from tutortrace.ingestion import service
from tutortrace.ingestion.service import ingest
from tutortrace.persistence import Store
from tutortrace.retrieval.search import search

LEGACY_VERSION = "text-v1:chars-1200:overlap-150"
CREATED_AT = "2026-10-13T00:00:00+00:00"


def labeled_pdf():
    data = make_pdf(("Energy introduction", "", "Photo-\nsynthesis stores energy."))
    with pymupdf.open(stream=data, filetype="pdf") as document:
        document.set_page_labels([
            {"startpage": 0, "prefix": "", "style": "r", "firstpagenum": 1},
            {"startpage": 2, "prefix": "", "style": "D", "firstpagenum": 1},
        ])
        return document.tobytes()


@pytest.fixture
def legacy(tmp_path):
    """Seed the actual frozen v1 schema with independently computed v1 hashes."""
    path = tmp_path / "tutortrace.sqlite3"
    data = labeled_pdf()
    document_id = sha256(data).hexdigest()
    chunk_ids = []
    texts = ("Energy introduction", "", "Photo- synthesis stores energy.")
    with sqlite3.connect(path) as connection:
        connection.executescript((Path(__file__).parent / "fixtures/schema_v1.sql").read_text())
        connection.execute("INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                           (document_id, "legacy.pdf", "pdf", data, len(data), 3, 2, "indexed", "[]", CREATED_AT, LEGACY_VERSION))
        for location, text in enumerate(texts, 1):
            unit_id = sha256(f"{document_id}:unit:{location}".encode()).hexdigest()
            connection.execute("INSERT INTO units VALUES (?, ?, ?, ?)", (unit_id, document_id, location, text))
            if text:
                chunk_id = sha256(f"{LEGACY_VERSION}:{unit_id}:0:{len(text)}:{text}".encode()).hexdigest()
                chunk_ids.append(chunk_id)
                connection.execute("INSERT INTO chunks VALUES (?, ?, ?, ?, ?)", (chunk_id, unit_id, 0, len(text), text))
        connection.execute("INSERT INTO ingestion_attempts VALUES (1, ?, ?, ?, ?, ?, ?, ?)",
                           ("legacy.pdf", document_id, document_id, "indexed", None, "Legacy ingestion", CREATED_AT))
    return path, data, document_id, chunk_ids


def snapshot(store):
    with store.connection() as connection:
        return {table: [tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY rowid")]
                for table in ("documents", "units", "chunks", "ingestion_attempts")}


def check_fts(store):
    with store.connection() as connection:
        # rank=1 also compares the external-content index to the chunks table.
        connection.execute("INSERT INTO chunks_fts(chunks_fts, rank) VALUES ('integrity-check', 1)")


def test_schema_v1_upgrade_preserves_existing_evidence(legacy, monkeypatch):
    path, data, document_id, chunk_ids = legacy
    store = Store(path)
    monkeypatch.setattr(models, "PIPELINE_VERSION", "future-pipeline")
    evidence = search(store, "photo")[0]
    assert evidence.pipeline_version == LEGACY_VERSION
    assert evidence.chunk_id in chunk_ids
    assert evidence.page_label is None  # Migration never guesses labels from text.
    assert evidence.location == 3
    assert store.resolve_evidence(evidence.chunk_id) == models.Evidence(**{
        **evidence.__dict__, "rank": None,
    })
    assert store.original(document_id) == data
    before = snapshot(store)
    for _ in range(3):
        assert snapshot(Store(path)) == before
    with store.connection() as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
        assert sum(row[1] == "page_label" for row in connection.execute("PRAGMA table_info(units)")) == 1
    check_fts(store)


def test_reupload_upgrades_pipeline_atomically_and_idempotently(legacy, monkeypatch):
    path, data, document_id, old_chunk_ids = legacy
    store = Store(path)
    result = ingest(store, "renamed.pdf", data)
    assert result.reindexed and not result.duplicate
    assert result.document.id == document_id
    assert result.document.filename == "legacy.pdf"
    assert result.document.created_at == CREATED_AT
    assert result.document.pipeline_version == models.PIPELINE_VERSION
    assert store.original(document_id) == data
    evidence = search(store, "photosynthesis")[0]
    assert evidence.citation == "legacy.pdf — PDF page 3 (label: 1)"
    assert evidence.text == evidence.unit_text[evidence.start:evidence.end]
    assert evidence.chunk_id not in old_chunk_ids
    assert search(store, "photo") == []  # Old FTS entries really were removed.
    with pytest.raises(ProvenanceError):
        store.resolve_evidence(old_chunk_ids[-1])
    assert "Reindexed from" in store.recent_attempts()[0]["message"]
    before = snapshot(store)
    def must_not_extract(_):
        pytest.fail("Ordinary duplicate uploads must not re-extract")
    monkeypatch.setattr(service, "extract_pdf", must_not_extract)
    duplicate = ingest(Store(path), "another-name.pdf", data)
    assert duplicate.duplicate and not duplicate.reindexed
    after = snapshot(store)
    assert all(before[table] == after[table] for table in ("documents", "units", "chunks"))
    assert len(after["ingestion_attempts"]) == len(before["ingestion_attempts"]) + 1
    check_fts(store)


def test_current_pipeline_bump_keeps_old_evidence_readable_and_reindexes(store, pdf_bytes, monkeypatch):
    first = ingest(store, "current.pdf", pdf_bytes)
    old_evidence = search(store, "gravity")[0]
    monkeypatch.setattr(models, "PIPELINE_VERSION", "test-next-pipeline")
    assert search(store, "gravity")[0] == old_evidence
    result = ingest(store, "current.pdf", pdf_bytes)
    assert result.reindexed and result.document.id == first.document.id
    assert result.document.pipeline_version == "test-next-pipeline"
    assert search(store, "gravity")[0].chunk_id != old_evidence.chunk_id
    assert ingest(store, "current.pdf", pdf_bytes).duplicate


def test_failed_reindex_restores_all_old_rows_and_index(legacy):
    path, data, _, _ = legacy
    store = Store(path)
    before = snapshot(store)
    with store.connection() as connection:
        connection.execute("""CREATE TRIGGER fail_reindex BEFORE INSERT ON chunks
            WHEN new.text LIKE 'Photosynthesis%' BEGIN SELECT RAISE(ABORT, 'injected reindex failure'); END""")
    with pytest.raises(StorageError):
        ingest(store, "legacy.pdf", data)
    reopened = Store(path)
    assert snapshot(reopened) == before
    assert search(reopened, "photo")[0].pipeline_version == LEGACY_VERSION
    assert search(reopened, "photosynthesis") == []
    check_fts(reopened)


def test_process_exit_mid_reindex_leaves_old_evidence_intact(legacy):
    path, _, _, _ = legacy
    store = Store(path)
    before = snapshot(store)
    with store.connection() as connection:
        connection.execute("CREATE TRIGGER crash_reindex BEFORE INSERT ON chunks BEGIN SELECT crash_process(); END")
    script = """
from contextlib import contextmanager
import os, sys
from tutortrace.persistence import Store
from tutortrace.ingestion.service import ingest
class CrashStore(Store):
    @contextmanager
    def connection(self):
        with super().connection() as connection:
            connection.create_function('crash_process', 0, lambda: os._exit(23))
            yield connection
store = CrashStore(sys.argv[1])
document = store.list_documents()[0]
ingest(store, document.filename, store.original(document.id))
"""
    completed = subprocess.run([sys.executable, "-c", script, str(path)], capture_output=True, timeout=60)
    assert completed.returncode == 23, completed.stderr.decode(errors="replace")
    assert snapshot(Store(path)) == before
    assert search(Store(path), "photo")[0].pipeline_version == LEGACY_VERSION
    check_fts(Store(path))


def test_extraction_failure_does_not_destroy_old_index(legacy, monkeypatch):
    path, data, _, _ = legacy
    store = Store(path)
    before = snapshot(store)
    def fail(_):
        raise InvalidDocumentError("Injected extraction failure")
    monkeypatch.setattr(service, "extract_pdf", fail)
    with pytest.raises(InvalidDocumentError):
        ingest(store, "legacy.pdf", data)
    after = snapshot(store)
    assert all(before[table] == after[table] for table in ("documents", "units", "chunks"))
    assert store.recent_attempts()[0]["status"] == "failed"
    assert search(store, "photo")


def test_concurrent_migration_and_upgrade_is_idempotent(legacy):
    path, data, _, _ = legacy
    def upgrade(_):
        return ingest(Store(path), "legacy.pdf", data)
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(upgrade, range(4)))
    assert sum(result.reindexed for result in results) == 1
    assert sum(result.duplicate for result in results) == 3
    store = Store(path)
    assert len(search(store, "photosynthesis")) == 1
    assert search(store, "photo") == []
    check_fts(store)


def test_stale_writer_cannot_overwrite_another_pipeline(legacy):
    path, data, document_id, _ = legacy
    store = Store(path)
    ingest(store, "legacy.pdf", data)
    from tutortrace.ingestion.pdf import extract_pdf
    from tutortrace.retrieval.chunking import chunk_units
    extraction = extract_pdf(data)
    with pytest.raises(StorageError, match="changed during extraction"):
        store.save_document(document_id, "legacy.pdf", "pdf", data, extraction,
                            chunk_units(document_id, extraction.units, pipeline_version="stale-version"),
                            pipeline_version="stale-version", expected_pipeline_version=LEGACY_VERSION)
    assert store.get_document(document_id).pipeline_version == models.PIPELINE_VERSION


@pytest.mark.parametrize("field,value", [("text", "Fake energy"), ("start", 1)])
def test_old_pipeline_corruption_still_detected(legacy, field, value):
    path, _, _, chunk_ids = legacy
    store = Store(path)
    with store.connection() as connection:
        connection.execute(f"UPDATE chunks SET {field} = ? WHERE id = ?", (value, chunk_ids[0]))
    with pytest.raises(ProvenanceError):
        store.resolve_evidence(chunk_ids[0])
    with pytest.raises(ProvenanceError):
        search(store, "energy")


def test_reindex_rejects_corrupted_original(legacy):
    path, data, document_id, _ = legacy
    store = Store(path)
    with store.connection() as connection:
        connection.execute("UPDATE documents SET original = ? WHERE id = ?", (b"corrupt", document_id))
    with pytest.raises(ProvenanceError):
        ingest(store, "legacy.pdf", data)
    assert store.get_document(document_id).pipeline_version == LEGACY_VERSION


def test_migration_failure_rolls_back_ddl_and_version(legacy, monkeypatch):
    path, data, document_id, _ = legacy
    monkeypatch.setitem(persistence.MIGRATIONS, 2, (*persistence.MIGRATIONS[2], "INVALID MIGRATION SQL"))
    with pytest.raises(StorageError):
        Store(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        assert "page_label" not in [row[1] for row in connection.execute("PRAGMA table_info(units)")]
        assert connection.execute("SELECT original FROM documents WHERE id = ?", (document_id,)).fetchone()[0] == data
        assert connection.execute("SELECT count(*) FROM chunks_fts WHERE chunks_fts MATCH 'photo'").fetchone()[0] == 1


def test_new_schema_creation_is_atomic(tmp_path, monkeypatch):
    path = tmp_path / "new.sqlite3"
    monkeypatch.setitem(persistence.MIGRATIONS, 2, ("INVALID MIGRATION SQL",))
    with pytest.raises(StorageError):
        Store(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchone()[0] == 0


def test_unknown_unversioned_schema_not_overwritten(tmp_path):
    path = tmp_path / "unknown.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE important(text)")
        connection.execute("INSERT INTO important VALUES ('keep me')")
    with pytest.raises(StorageError, match="Unversioned nonempty"):
        Store(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT text FROM important").fetchone()[0] == "keep me"
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 0


def test_new_database_uses_latest_schema(store):
    with store.connection() as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == persistence.SCHEMA_VERSION == 2


def test_concurrent_creation_uses_latest_schema(tmp_path):
    path = tmp_path / "new.sqlite3"
    with ThreadPoolExecutor(max_workers=4) as executor:
        stores = list(executor.map(lambda _: Store(path), range(4)))
    for store in stores:
        assert store.list_documents() == []
        with store.connection() as connection:
            assert connection.execute("PRAGMA user_version").fetchone()[0] == 2


def test_upgraded_evidence_survives_fresh_process(legacy):
    path, data, document_id, _ = legacy
    ingest(Store(path), "legacy.pdf", data)
    script = """
import json, sys
from tutortrace.persistence import Store
from tutortrace.retrieval.search import search
from tutortrace.models import digest
store = Store(sys.argv[1])
evidence = search(store, 'photosynthesis')[0]
print(json.dumps([evidence.location, evidence.page_label, evidence.pipeline_version, digest(store.original(evidence.document_id))]))
"""
    result = subprocess.run([sys.executable, "-c", script, str(path)], capture_output=True, text=True, check=True, timeout=60)
    assert json.loads(result.stdout) == [3, "1", models.PIPELINE_VERSION, document_id]


def test_forged_persisted_pipeline_version_is_detected(legacy):
    path, _, _, _ = legacy
    store = Store(path)
    with store.connection() as connection:
        connection.execute("UPDATE documents SET pipeline_version = 'forged-version'")
    with pytest.raises(ProvenanceError):
        search(store, "photo")


def test_app_displays_reindex_status_and_exact_label(legacy, monkeypatch):
    from streamlit.testing.v1 import AppTest
    path, data, _, _ = legacy
    monkeypatch.setenv("TUTORTRACE_DATA_DIR", str(path.parent))
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=30).run()
    assert not app.exception
    app.file_uploader[0].set_value(("renamed.pdf", data, "application/pdf"))
    next(button for button in app.button if button.label == "Ingest documents").click().run()
    assert not app.exception and not app.error
    assert any("Reindexed legacy.pdf" in item.value for item in app.success)
    app.text_input[0].set_value("photosynthesis")
    next(button for button in app.button if button.label == "Find evidence").click().run()
    assert not app.exception and not app.error
    assert any("legacy.pdf — PDF page 3 (label: 1)" in item.value for item in app.text)


def test_pdf_dehyphenation_labels_and_physical_provenance(store):
    data = labeled_pdf()
    result = ingest(store, "chapter.pdf", data)
    evidence = search(Store(store.path), "photosynthesis")[0]
    assert evidence.location == 3
    assert evidence.page_label == "1"
    assert evidence.citation == "chapter.pdf — PDF page 3 (label: 1)"
    assert evidence.unit_text[evidence.start:evidence.end] == evidence.text
    assert store.original(result.document.id) == data
    assert search(store, "introduction")[0].citation == "chapter.pdf — PDF page 1 (label: i)"
    with store.connection() as connection:
        assert tuple(connection.execute("SELECT location, text, page_label FROM units WHERE location=2").fetchone()) == (2, "", "ii")


def test_pdf_ligatures_expanded(store):
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_htmlbox(pymupdf.Rect(20, 20, 500, 500), "<p>Energy of\ufb01ce and \ufb02ow experiments.</p>")
        assert "\ufb01" in page.get_text()  # The fixture genuinely contains a ligature.
        data = document.tobytes()
    ingest(store, "ligatures.pdf", data)
    evidence = search(store, "office")[0]
    assert "office and flow" in evidence.text
    assert "\ufb01" not in evidence.text
    assert evidence.location == 1


def test_page_text_is_never_used_to_guess_labels(store):
    ingest(store, "unlabeled.pdf", make_pdf(("Cover", "Contents", "Printed page 1: gravity.")))
    evidence = search(store, "gravity")[0]
    assert evidence.page_label is None
    assert evidence.citation == "unlabeled.pdf, page 3"


def test_hyphenation_does_not_join_pages_blocks_or_inline_compounds(store):
    with pymupdf.open() as document:
        first = document.new_page()
        first.insert_text((50, 50), "photo-")
        first.insert_text((50, 350), "synthesis well-being 10-\n20")
        second = document.new_page()
        second.insert_text((50, 50), "cross-")
        third = document.new_page()
        third.insert_text((50, 50), "page")
        data = document.tobytes()
    ingest(store, "boundaries.pdf", data)
    assert search(store, "photosynthesis") == []
    assert search(store, "crosspage") == []
    assert search(store, "wellbeing") == []
    assert "well-being 10- 20" in search(store, "synthesis")[0].text


@pytest.mark.parametrize("text,query", [
    ("Straße", "Straße"), ("Straße", "STRAẞE"), ("café", "CAFE"),
    ("café", "cafe\u0301"), ("İSTANBUL", "İSTANBUL"),
    ("Δύναμη", "δύναμη"), ("Динамика", "ДИНАМИКА"),
])
def test_queries_use_same_unicode61_normalization_as_index(store, text, query):
    ingest(store, "language.pptx", make_pptx((text,)))
    results = search(store, query)
    assert len(results) == 1
    assert results[0].text == text
    assert results[0].citation == "language.pptx, slide 1"


def test_german_transliteration_is_not_claimed(store):
    ingest(store, "german.pptx", make_pptx(("Straße",)))
    assert search(store, "strasse") == []
    assert store.query_terms("Straße") == ["straße"]
