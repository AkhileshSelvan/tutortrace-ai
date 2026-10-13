"""Future providers consume retrieved evidence and return evidence IDs, not citations.

Any future caller must resolve cited chunk IDs through the store before displaying
an answer. Defining this interface does not implement generation or grounding.
"""

from dataclasses import dataclass
from typing import Protocol, Sequence

from tutortrace.models import Evidence


@dataclass(frozen=True)
class ProviderAnswer:
    text: str
    cited_chunk_ids: tuple[str, ...]
    provider: str
    model: str


class AnswerProvider(Protocol):
    def answer(self, question: str, evidence: Sequence[Evidence]) -> ProviderAnswer: ...
