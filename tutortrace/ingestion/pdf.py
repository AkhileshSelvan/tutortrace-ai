"""Extract text from PDF pages while preserving physical page numbers."""

import base64
import json
from pathlib import Path
import subprocess
import sys

from tutortrace.errors import DocumentLimitError, InvalidDocumentError, PasswordProtectedError
from tutortrace.models import ExtractedUnit, Extraction

MAX_UNITS = 2000
MAX_TEXT_CHARS = 5_000_000
PDF_TIMEOUT_SECONDS = 60


def extract_pdf(data: bytes) -> Extraction:
    result = _worker(data, "extract", str(MAX_UNITS), str(MAX_TEXT_CHARS))
    return Extraction(tuple(ExtractedUnit(**unit) for unit in result["units"]), tuple(result["warnings"]))


def render_pdf_page(data: bytes, location: int) -> bytes:
    """Render the physical page in an isolated process, not a Streamlit thread."""
    result = _worker(data, "preview", str(location))
    return base64.b64decode(result["png"])


def _worker(data: bytes, operation: str, *arguments: str) -> dict:
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "tutortrace.ingestion.pdf_worker", operation, *arguments],
            input=data, capture_output=True, timeout=PDF_TIMEOUT_SECONDS,
            cwd=Path(__file__).resolve().parents[2],
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
    except subprocess.TimeoutExpired as exc:
        raise DocumentLimitError(f"PDF processing exceeded {PDF_TIMEOUT_SECONDS} seconds.") from exc
    except OSError as exc:
        raise InvalidDocumentError("The local PDF worker could not be started.") from exc
    if completed.returncode != 0:
        raise InvalidDocumentError("The PDF worker failed. The document may contain an unsupported structure.")
    try:
        result = json.loads(completed.stdout)
    except (ValueError, UnicodeError) as exc:
        raise InvalidDocumentError("The PDF worker returned an unreadable response.") from exc
    if "error" in result:
        error_type = {"password_protected": PasswordProtectedError, "document_limit": DocumentLimitError}.get(result["error"], InvalidDocumentError)
        raise error_type(result["message"])
    return result


def _extract_pdf(data: bytes, max_units: int, max_text_chars: int) -> Extraction:
    """Called only by the standalone worker process."""
    import pymupdf

    if b"%PDF-" not in data[:1024]:
        raise InvalidDocumentError("The file does not have a PDF header.")
    try:
        with pymupdf.open(stream=data, filetype="pdf") as document:
            if not document.is_pdf:
                raise InvalidDocumentError("The uploaded file is not a PDF.")
            if document.needs_pass:
                raise PasswordProtectedError("Password-protected PDFs are not supported. Upload an unlocked copy.")
            if len(document) > max_units:
                raise DocumentLimitError(f"PDF exceeds the {max_units}-page limit.")
            units = []
            total = 0
            for number, page in enumerate(document, 1):
                text = " ".join(page.get_text("text", sort=True).split())
                total += len(text)
                if total > max_text_chars:
                    raise DocumentLimitError("Extracted text exceeds the 5-million-character limit.")
                units.append(ExtractedUnit(number, text))
            warnings = ["Text extraction only: images, diagrams and scanned text are not interpreted."]
            if document.is_repaired:
                warnings.append("PyMuPDF repaired the PDF structure; check extracted text against the original.")
            blank = sum(not unit.text for unit in units)
            if blank:
                warnings.append(f"{blank} page(s) have no extractable text; their page numbers are retained.")
            return Extraction(tuple(units), tuple(warnings))
    except (InvalidDocumentError, DocumentLimitError):
        raise
    except Exception as exc:
        raise InvalidDocumentError("PDF could not be read. It may be corrupted or use an unsupported structure.") from exc
