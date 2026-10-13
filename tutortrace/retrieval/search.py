"""Literal keyword retrieval with no arbitrary SQL/FTS query syntax exposure."""

from tutortrace.errors import SearchQueryError
from tutortrace.models import Evidence
from tutortrace.persistence import Store

STOP_WORDS = frozenset("a an and are as at be by can do does explain for from how i in is it me of on or that the this to was what when where which who why with".split())


def search(store: Store, query: str, limit: int = 5, document_id: str | None = None) -> list[Evidence]:
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 50:
        raise SearchQueryError("Result count must be between 1 and 50.")
    if len(query) > 1000:
        raise SearchQueryError("Search is limited to 1,000 characters.")
    # Let the index's tokenizer perform case/diacritic normalization too. Python
    # casefold expands e.g. sharp-s to 'ss', unlike SQLite unicode61.
    tokens = list(dict.fromkeys(store.query_terms(query)))
    tokens = [token for token in tokens if token not in STOP_WORDS]
    if not tokens:
        return []
    if len(tokens) > 64:
        raise SearchQueryError("Use at most 64 distinct search terms.")
    # OR supports natural questions; BM25 orders matching passages, not truth/confidence.
    expression = " OR ".join('"' + token.replace('"', '""') + '"' for token in tokens)
    return store.search(expression, limit, document_id)
