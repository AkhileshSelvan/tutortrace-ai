"""SQLite source ledger and FTS index committed together, including original bytes."""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from tutortrace.errors import ProvenanceError, StorageError
from tutortrace.models import (
    PIPELINE_VERSION, Chunk, Document, Evidence, Extraction, IngestionResult,
    chunk_identifier, digest, unit_identifier,
)

SCHEMA_VERSION = 1
SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK(source_type IN ('pdf', 'pptx')),
    original BLOB NOT NULL,
    byte_size INTEGER NOT NULL,
    unit_count INTEGER NOT NULL,
    chunk_count INTEGER NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('indexed', 'empty')),
    warnings TEXT NOT NULL,
    created_at TEXT NOT NULL,
    pipeline_version TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS units (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id),
    location INTEGER NOT NULL CHECK(location >= 1),
    text TEXT NOT NULL,
    UNIQUE(document_id, location)
);
CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    unit_id TEXT NOT NULL REFERENCES units(id),
    start INTEGER NOT NULL CHECK(start >= 0),
    end INTEGER NOT NULL CHECK(end > start),
    text TEXT NOT NULL,
    UNIQUE(unit_id, start, end)
);
CREATE INDEX IF NOT EXISTS chunks_by_unit ON chunks(unit_id);
CREATE TABLE IF NOT EXISTS ingestion_attempts (
    id INTEGER PRIMARY KEY,
    filename TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    document_id TEXT REFERENCES documents(id),
    status TEXT NOT NULL CHECK(status IN ('indexed', 'empty', 'duplicate', 'failed')),
    error_code TEXT,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text, content='chunks', content_rowid='rowid', tokenize='unicode61'
);
CREATE TRIGGER IF NOT EXISTS chunks_insert AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, text) VALUES (new.rowid, new.text);
END;
CREATE TRIGGER IF NOT EXISTS chunks_delete AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES ('delete', old.rowid, old.text);
END;
CREATE TRIGGER IF NOT EXISTS chunks_update AFTER UPDATE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES ('delete', old.rowid, old.text);
    INSERT INTO chunks_fts(rowid, text) VALUES (new.rowid, new.text);
END;
PRAGMA user_version = 1;
"""

DOCUMENT_COLUMNS = "id, filename, source_type, byte_size, unit_count, chunk_count, status, warnings, created_at, pipeline_version"
EVIDENCE_COLUMNS = """
    c.id AS chunk_id, c.unit_id, d.id AS document_id, d.filename,
    d.source_type, u.location, c.start, c.end, c.text, u.text AS unit_text
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _document(row: sqlite3.Row) -> Document:
    values = dict(row)
    values["warnings"] = tuple(json.loads(values["warnings"]))
    return Document(**values)


def _evidence(row: sqlite3.Row) -> Evidence:
    evidence = Evidence(**dict(row))
    if (
        evidence.unit_id != unit_identifier(evidence.document_id, evidence.location)
        or not 0 <= evidence.start < evidence.end <= len(evidence.unit_text)
        or evidence.text != evidence.unit_text[evidence.start:evidence.end]
        or evidence.chunk_id != chunk_identifier(evidence.unit_id, evidence.start, evidence.end, evidence.text)
    ):
        raise ProvenanceError("Stored evidence failed its provenance check. Restore or re-ingest the source.")
    return evidence


class Store:
    def __init__(self, database: str | Path):
        self.path = Path(database).resolve()
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.connection() as connection:
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                if version not in (0, SCHEMA_VERSION):
                    raise StorageError(f"Database schema {version} is not supported by this application.")
                connection.execute("PRAGMA journal_mode = WAL")
                connection.executescript(SCHEMA)
        except OSError as exc:
            raise StorageError("Could not create the local data directory. Check available space and permissions.") from exc

    @contextmanager
    def connection(self):
        connection = None
        try:
            connection = sqlite3.connect(self.path, timeout=15)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            with connection:
                yield connection
        except sqlite3.Error as exc:
            raise StorageError("Local database operation failed. Check disk space, permissions and SQLite FTS5 support.") from exc
        finally:
            if connection is not None:
                connection.close()

    def get_document(self, document_id: str) -> Document | None:
        with self.connection() as connection:
            row = connection.execute(f"SELECT {DOCUMENT_COLUMNS} FROM documents WHERE id = ?", (document_id,)).fetchone()
            return _document(row) if row else None

    def list_documents(self) -> list[Document]:
        with self.connection() as connection:
            rows = connection.execute(f"SELECT {DOCUMENT_COLUMNS} FROM documents ORDER BY created_at DESC, id").fetchall()
            return [_document(row) for row in rows]

    def original(self, document_id: str) -> bytes:
        with self.connection() as connection:
            row = connection.execute("SELECT original FROM documents WHERE id = ?", (document_id,)).fetchone()
        if row is None:
            raise ProvenanceError("This original document does not exist in the source ledger.")
        data = bytes(row[0])
        if digest(data) != document_id:
            raise ProvenanceError("Original document bytes failed their SHA-256 integrity check.")
        return data

    def recent_attempts(self, limit: int = 20) -> list[dict]:
        with self.connection() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM ingestion_attempts ORDER BY id DESC LIMIT ?", (limit,)
            )]

    @staticmethod
    def _attempt(connection, filename, content_hash, document_id, status, message, error_code=None):
        connection.execute(
            """INSERT INTO ingestion_attempts
            (filename, content_hash, document_id, status, error_code, message, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (filename, content_hash, document_id, status, error_code, message, _now()),
        )

    def record_failure(self, filename: str, content_hash: str, error_code: str, message: str):
        with self.connection() as connection:
            self._attempt(connection, filename, content_hash, None, "failed", message, error_code)

    def record_duplicate(self, document: Document, filename: str) -> IngestionResult:
        with self.connection() as connection:
            self._attempt(connection, filename, document.id, document.id, "duplicate", "Identical source bytes already preserved.")
        return IngestionResult(document, duplicate=True)

    def save_document(self, document_id: str, filename: str, source_type: str, data: bytes,
                      extraction: Extraction, chunks: list[Chunk]) -> IngestionResult:
        with self.connection() as connection:
            # Serializes the duplicate check and write across independent app sessions.
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(f"SELECT {DOCUMENT_COLUMNS} FROM documents WHERE id = ?", (document_id,)).fetchone()
            if row:
                self._attempt(connection, filename, document_id, document_id, "duplicate", "Identical source bytes already preserved.")
                return IngestionResult(_document(row), duplicate=True)
            status = "indexed" if chunks else "empty"
            warnings = list(extraction.warnings)
            if not chunks:
                warnings.append("No extractable text: original preserved, but no searchable passages. OCR is not implemented.")
            created_at = _now()
            connection.execute(
                "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (document_id, filename, source_type, data, len(data), len(extraction.units), len(chunks),
                 status, json.dumps(warnings), created_at, PIPELINE_VERSION),
            )
            connection.executemany("INSERT INTO units VALUES (?, ?, ?, ?)", [
                (unit_identifier(document_id, unit.location), document_id, unit.location, unit.text)
                for unit in extraction.units
            ])
            connection.executemany("INSERT INTO chunks VALUES (?, ?, ?, ?, ?)", [
                (chunk.id, chunk.unit_id, chunk.start, chunk.end, chunk.text) for chunk in chunks
            ])
            self._attempt(connection, filename, document_id, document_id, status, f"Preserved {len(extraction.units)} source units; indexed {len(chunks)} passages.")
            document = Document(document_id, filename, source_type, len(data), len(extraction.units),
                                len(chunks), status, tuple(warnings), created_at, PIPELINE_VERSION)
            return IngestionResult(document, duplicate=False)

    def resolve_evidence(self, chunk_id: str) -> Evidence:
        with self.connection() as connection:
            row = connection.execute(f"""SELECT {EVIDENCE_COLUMNS}
                FROM chunks c JOIN units u ON c.unit_id = u.id
                JOIN documents d ON u.document_id = d.id WHERE c.id = ?""", (chunk_id,)).fetchone()
        if row is None:
            raise ProvenanceError("The requested passage does not exist in the source ledger.")
        return _evidence(row)

    def search(self, expression: str, limit: int, document_id: str | None = None) -> list[Evidence]:
        parameters: list = [expression]
        document_filter = ""
        if document_id is not None:
            document_filter = "AND d.id = ?"
            parameters.append(document_id)
        parameters.append(limit)
        with self.connection() as connection:
            rows = connection.execute(f"""SELECT {EVIDENCE_COLUMNS}, bm25(chunks_fts) AS rank
                FROM chunks_fts JOIN chunks c ON chunks_fts.rowid = c.rowid
                JOIN units u ON c.unit_id = u.id JOIN documents d ON u.document_id = d.id
                WHERE chunks_fts MATCH ? {document_filter}
                ORDER BY rank, d.id, u.location, c.start LIMIT ?""", parameters).fetchall()
        return [_evidence(row) for row in rows]
