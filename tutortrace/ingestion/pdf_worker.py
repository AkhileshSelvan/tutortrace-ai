"""Private subprocess entry point: PDF bytes on stdin, one JSON result on stdout.

PyMuPDF is not thread-safe. Never import Streamlit or open the source database
here. The caller owns timeout/termination and commits only a completed extraction.
"""

import base64
from dataclasses import asdict
import json
import sys

import pymupdf

from tutortrace.errors import InvalidDocumentError, TutorTraceError
from tutortrace.ingestion.pdf import _extract_pdf


def main():
    pymupdf.TOOLS.mupdf_display_errors(False)
    pymupdf.TOOLS.mupdf_display_warnings(False)
    data = sys.stdin.buffer.read()
    try:
        operation = sys.argv[1]
        if operation == "extract":
            result = asdict(_extract_pdf(data, int(sys.argv[2]), int(sys.argv[3])))
        elif operation == "preview":
            location = int(sys.argv[2])
            with pymupdf.open(stream=data, filetype="pdf") as document:
                if not 1 <= location <= len(document):
                    raise InvalidDocumentError("The requested PDF page does not exist.")
                page = document[location - 1]
                scale = min(1.5, 1600 / max(page.rect.width, page.rect.height))
                png = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).tobytes("png")
                result = {"png": base64.b64encode(png).decode("ascii")}
        else:
            raise InvalidDocumentError("Unknown PDF worker operation.")
    except TutorTraceError as exc:
        result = {"error": exc.code, "message": str(exc)}
    except Exception:
        result = {"error": "invalid_document", "message": "PDF processing failed. The document may be corrupted or unsupported."}
    sys.stdout.buffer.write(json.dumps(result).encode("utf-8"))


if __name__ == "__main__":
    main()
