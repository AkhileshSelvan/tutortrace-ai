-- Milestone 1 schema from commit 317a0f20fd4c76c1b05774a0e4c8ef2cf63a443d.

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
