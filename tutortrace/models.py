"""Immutable types shared by ingestion, storage, retrieval and future providers."""

from dataclasses import dataclass
from hashlib import sha256
from typing import Literal

SourceType = Literal["pdf", "pptx"]
PIPELINE_VERSION = "text-v1:chars-1200:overlap-150"


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def unit_identifier(document_id: str, location: int) -> str:
    return digest(f"{document_id}:unit:{location}".encode())


def chunk_identifier(unit_id: str, start: int, end: int, text: str) -> str:
    return digest(f"{PIPELINE_VERSION}:{unit_id}:{start}:{end}:{text}".encode())


@dataclass(frozen=True)
class ExtractedUnit:
    location: int  # Original one-based page or slide; blank units are retained.
    text: str


@dataclass(frozen=True)
class Extraction:
    units: tuple[ExtractedUnit, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class Chunk:
    id: str
    unit_id: str
    start: int  # Offsets into the stored normalized source-unit text.
    end: int
    text: str


@dataclass(frozen=True)
class Document:
    id: str
    filename: str
    source_type: SourceType
    byte_size: int
    unit_count: int
    chunk_count: int
    status: str
    warnings: tuple[str, ...]
    created_at: str
    pipeline_version: str


@dataclass(frozen=True)
class IngestionResult:
    document: Document
    duplicate: bool


@dataclass(frozen=True)
class Evidence:
    chunk_id: str
    unit_id: str
    document_id: str
    filename: str
    source_type: SourceType
    location: int
    start: int
    end: int
    text: str
    unit_text: str
    rank: float | None = None  # SQLite BM25 rank, not confidence/probability.

    @property
    def citation(self) -> str:
        label = "page" if self.source_type == "pdf" else "slide"
        return f"{self.filename}, {label} {self.location}"
