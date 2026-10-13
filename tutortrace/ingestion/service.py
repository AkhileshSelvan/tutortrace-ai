"""Upload validation and orchestration with durable success/failure metadata."""

from pathlib import PurePosixPath

from tutortrace.errors import DocumentLimitError, InvalidDocumentError, StorageError, TutorTraceError, UnsupportedFileError
from tutortrace.ingestion.pdf import extract_pdf
from tutortrace.ingestion.pptx import extract_pptx
from tutortrace.models import IngestionResult, digest
from tutortrace.persistence import Store
from tutortrace.retrieval.chunking import chunk_units

MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def safe_filename(filename: str) -> str:
    # Filenames are display metadata only. They never form a storage path.
    name = PurePosixPath(filename.replace("\\", "/")).name
    name = "".join(character for character in name if character.isprintable()).strip()
    if len(name) > 240:
        suffix = PurePosixPath(name).suffix
        name = name[:240 - len(suffix)] + suffix if len(suffix) < 240 else name[:240]
    return name or "unnamed"


def ingest(store: Store, filename: str, data: bytes) -> IngestionResult:
    filename = safe_filename(filename)
    document_id = digest(data)
    try:
        extension = PurePosixPath(filename).suffix.lower()
        if extension not in (".pdf", ".pptx"):
            raise UnsupportedFileError("Unsupported file type. Upload a .pdf or .pptx file.")
        if not data:
            raise InvalidDocumentError("The uploaded file contains zero bytes.")
        if len(data) > MAX_UPLOAD_BYTES:
            raise DocumentLimitError("File exceeds the 50 MiB upload limit.")
        source_type = extension[1:]
        existing = store.get_document(document_id)
        if existing:
            if existing.source_type != source_type:
                raise InvalidDocumentError("These bytes were previously uploaded as a different file type. Use the correct extension.")
            return store.record_duplicate(existing, filename)
        extraction = extract_pdf(data) if source_type == "pdf" else extract_pptx(data)
        chunks = chunk_units(document_id, extraction.units)
        return store.save_document(document_id, filename, source_type, data, extraction, chunks)
    except StorageError:
        # The database cannot reliably log its own failure; preserve the original error.
        raise
    except TutorTraceError as exc:
        store.record_failure(filename, document_id, exc.code, str(exc))
        raise
