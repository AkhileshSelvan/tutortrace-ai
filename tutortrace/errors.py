"""Expected failures suitable for presentation to a user."""


class TutorTraceError(Exception):
    code = "tutortrace_error"


class UnsupportedFileError(TutorTraceError):
    code = "unsupported_file"


class InvalidDocumentError(TutorTraceError):
    code = "invalid_document"


class PasswordProtectedError(InvalidDocumentError):
    code = "password_protected"


class DocumentLimitError(InvalidDocumentError):
    code = "document_limit"


class StorageError(TutorTraceError):
    code = "storage_error"


class ProvenanceError(TutorTraceError):
    code = "provenance_error"


class SearchQueryError(TutorTraceError):
    code = "search_query_error"
