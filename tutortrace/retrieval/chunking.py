"""Overlapping text chunks bounded by a single physical source unit."""

from tutortrace import models
from tutortrace.models import Chunk, ExtractedUnit, chunk_identifier, unit_identifier

CHUNK_SIZE = 1200
OVERLAP = 150


def chunk_units(document_id: str, units: tuple[ExtractedUnit, ...], *, pipeline_version: str | None = None) -> list[Chunk]:
    pipeline_version = models.PIPELINE_VERSION if pipeline_version is None else pipeline_version
    chunks = []
    for unit in units:
        unit_id = unit_identifier(document_id, unit.location)
        start = 0
        while start < len(unit.text):
            end = min(start + CHUNK_SIZE, len(unit.text))
            if end < len(unit.text):
                boundary = unit.text.rfind(" ", start + CHUNK_SIZE // 2, end)
                if boundary > start:
                    end = boundary
            text = unit.text[start:end]
            chunks.append(Chunk(chunk_identifier(unit_id, start, end, text, pipeline_version=pipeline_version), unit_id, start, end, text))
            if end == len(unit.text):
                break
            start = end - OVERLAP
            # Avoid starting mid-word when a word boundary exists inside the overlap.
            boundary = unit.text.find(" ", start, end)
            if boundary >= 0:
                start = boundary + 1
    return chunks
