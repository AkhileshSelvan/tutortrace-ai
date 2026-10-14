"""Question retrieval, rank fusion and bounded provenance-preserving context."""

from dataclasses import dataclass
import json
import math
import sqlite3

from tutortrace.errors import SearchQueryError
from tutortrace.models import Evidence, digest
from tutortrace.providers.llm import InferenceError
from tutortrace.retrieval.search import search


@dataclass(frozen=True)
class ContextConfig:
    max_passages: int = 5
    max_characters: int = 3600
    candidate_limit: int = 500
    semantic_min_similarity: float = 0.35

    def __post_init__(self):
        if not 1 <= self.max_passages <= 12 or not 1200 <= self.max_characters <= 12000 or not 1 <= self.candidate_limit <= 5000:
            raise SearchQueryError("Invalid context limits.")
        if not -1 <= self.semantic_min_similarity <= 1:
            raise SearchQueryError("Invalid semantic similarity threshold.")


@dataclass(frozen=True)
class EvidenceContext:
    evidence: tuple[Evidence, ...]
    mode: str
    warnings: tuple[str, ...] = ()


def cosine(left, right):
    if len(left) != len(right) or not left or not all(type(v) in (int, float) and math.isfinite(v) for v in [*left, *right]):
        raise InferenceError("Invalid embedding dimensions or values.")
    denominator = math.sqrt(sum(x*x for x in left) * sum(x*x for x in right))
    if not denominator:
        raise InferenceError("Embedding vector has zero magnitude.")
    return sum(x*y for x, y in zip(left, right)) / denominator


def semantic_rank(store, question, document_ids, embedder, config):
    candidates = store.evidence_candidates(document_ids, config.candidate_limit + 1)
    if len(candidates) > config.candidate_limit:
        raise InferenceError(f"Semantic retrieval is limited to {config.candidate_limit} passages; narrow the document selection.")
    if not candidates:
        return []
    fingerprint = embedder.fingerprint()
    # Disposable cache is separate from the source ledger. Keys include the model
    # digest and text hash, so model replacement/re-indexing cannot reuse stale data.
    cache = sqlite3.connect(store.path.with_suffix(".embeddings.sqlite3"), timeout=15)
    try:
        with cache:
            cache.execute("CREATE TABLE IF NOT EXISTS vectors (model TEXT, chunk TEXT, text_hash TEXT, vector TEXT, PRIMARY KEY(model, chunk))")
            vectors = {}
            missing = []
            for item in candidates:
                row = cache.execute("SELECT vector FROM vectors WHERE model=? AND chunk=? AND text_hash=?",
                                    (fingerprint, item.chunk_id, digest(item.text.encode()))).fetchone()
                if row:
                    vectors[item.chunk_id] = json.loads(row[0])
                else:
                    missing.append(item)
            # One bounded request keeps the small embedding model loaded only for
            # this batch; keep_alive=0 releases it before answer generation.
            texts = [item.text for item in missing]
            new_vectors = embedder.embed(texts) if texts else []
            for item, vector in zip(missing, new_vectors, strict=True):
                vectors[item.chunk_id] = vector
                cache.execute("INSERT OR REPLACE INTO vectors VALUES (?, ?, ?, ?)",
                              (fingerprint, item.chunk_id, digest(item.text.encode()), json.dumps(vector)))
        query_vector = embedder.embed([question], query=True)[0]
        ranked = [(cosine(query_vector, vectors[item.chunk_id]), item) for item in candidates]
        ranked.sort(key=lambda pair: (-pair[0], pair[1].chunk_id))
        return [item for score, item in ranked if score >= config.semantic_min_similarity][:50]
    finally:
        cache.close()


def retrieve_context(store, question, *, document_ids=(), config=None, embedder=None):
    config = config or ContextConfig()
    if not isinstance(question, str) or not question.strip() or len(question) > 1000:
        raise SearchQueryError("Enter a question between 1 and 1,000 characters.")
    document_ids = tuple(dict.fromkeys(document_ids))
    if len(document_ids) > 50:
        raise SearchQueryError("Select at most 50 documents.")
    for document_id in document_ids:
        if store.get_document(document_id) is None:
            raise SearchQueryError("A selected document no longer exists.")
    lexical = []
    for scope in document_ids or (None,):
        lexical.extend(search(store, question, 50, scope))
    lexical.sort(key=lambda item: (item.rank, item.document_id, item.location, item.start))
    rankings = [lexical]
    warnings = []
    mode = "keyword"
    if embedder is not None:
        try:
            rankings.append(semantic_rank(store, question, document_ids, embedder, config))
            mode = "hybrid"
        except (InferenceError, sqlite3.Error, ValueError, TypeError, KeyError) as exc:
            warnings.append("Semantic retrieval unavailable; using keyword evidence only. " +
                            (str(exc) if isinstance(exc, InferenceError) else "The embedding cache or response could not be read."))
    scores, candidates = {}, {}
    for ranking in rankings:
        for position, item in enumerate(ranking, 1):
            scores[item.chunk_id] = scores.get(item.chunk_id, 0) + 1 / (60 + position)
            candidates[item.chunk_id] = item
    selected = []
    characters = 0
    for chunk_id in sorted(scores, key=lambda key: (-scores[key], key)):
        item = candidates[chunk_id]
        # Keep identical text in DIFFERENT sources: it may matter for attribution.
        # Suppress redundant/mostly overlapping windows in the same source unit.
        if any(item.unit_id == old.unit_id and (item.text == old.text or
               max(0, min(item.end, old.end) - max(item.start, old.start)) >= 0.5 * min(len(item.text), len(old.text))) for old in selected):
            continue
        if characters + len(item.text) > config.max_characters:
            continue
        selected.append(item)
        characters += len(item.text)
        if len(selected) >= config.max_passages:
            break
    return EvidenceContext(tuple(selected), mode, tuple(warnings))
