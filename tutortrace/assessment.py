"""Source-exact recall exercises. No generated answer key is trusted.

Questions are deterministic cloze transformations of verified source sentences.
They assess recall, not general semantic understanding or arithmetic reasoning.
"""

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
import json
import re
import unicodedata

from tutortrace.errors import TutorTraceError
from tutortrace.models import digest
from tutortrace.retrieval.context import ContextConfig, retrieve_context
from tutortrace.retrieval.search import STOP_WORDS

GENERATOR_VERSION = "source-cloze-v1"
KINDS = ("mcq", "short", "numerical")
LEVELS = ("easy", "medium", "hard")
WORD = re.compile(r"[^\W\d_]+(?:[-'][^\W\d_]+)*", re.UNICODE)
NUMBER = re.compile(r"(?<![\w.,−–])[-+]?\d+(?:\.\d+)?(?![\w.,]\d)")


class AssessmentError(TutorTraceError):
    code = "assessment_error"


@dataclass(frozen=True)
class Question:
    id: str
    fact_id: str
    chunk_id: str
    sentence_start: int
    sentence_end: int
    answer_start: int
    answer_end: int
    kind: str
    difficulty: str
    prompt: str
    answer: str
    options: tuple[str, ...]
    quote: str

    def to_json(self):
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_json(cls, value):
        try:
            data = json.loads(value)
            data["options"] = tuple(data["options"])
            return cls(**data)
        except (ValueError, TypeError, KeyError) as exc:
            raise AssessmentError("Stored question is malformed.") from exc


@dataclass(frozen=True)
class Grade:
    status: str  # correct, incorrect, needs_review
    score: int | None
    feedback: str
    misconception: str | None


def normalize(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def sentences(text):
    # Do not split decimal points. Line breaks are boundaries, never page joins.
    for match in re.finditer(r"[^\n]+", text):
        start = match.start()
        for part in re.split(r"(?<=[.!?])\s+(?=[A-Z])", match.group()):
            offset = text.find(part, start, match.end())
            left = offset + len(part) - len(part.lstrip())
            right = offset + len(part.rstrip())
            if 25 <= right - left <= 450 and len(WORD.findall(text[left:right])) >= 4:
                yield left, right
            start = offset + len(part)


def _span(text, start, end, kind, difficulty):
    sentence = text[start:end]
    if kind == "numerical" or (kind == "mcq" and NUMBER.search(sentence)):
        numbers = list(NUMBER.finditer(sentence))
        if not numbers:
            return None
        # Last stated value usually follows the worked-example givens. This is
        # explicitly value recall, never a claim of having verified a calculation.
        selected = numbers[-1]
        if len(selected.group()) > 18:
            return None  # Keep deterministic distractors/hints within a modest decimal range.
        return start + selected.start(), start + selected.end()
    words = list(WORD.finditer(sentence))
    count = {"easy": 1, "medium": 2, "hard": 3}[difficulty]
    eligible = [i for i, word in enumerate(words) if word.group().lower() not in STOP_WORDS and len(word.group()) >= 4]
    if not eligible:
        return None
    index = eligible[-1]
    first = max(0, index - count + 1)
    return start + words[first].start(), start + words[index].end()


def _build(evidence, start, end, kind, difficulty):
    if (type(start) is not int or type(end) is not int or kind not in KINDS
            or difficulty not in LEVELS or (start, end) not in set(sentences(evidence.text))):
        raise AssessmentError("Unsupported question type, difficulty or source sentence.")
    span = _span(evidence.text, start, end, kind, difficulty)
    if span is None:
        return None
    left, right = span
    answer = evidence.text[left:right]
    quote = evidence.text[start:end]
    blank = evidence.text[start:left] + "[____]" + evidence.text[right:end]
    options = ()
    if kind == "mcq":
        if NUMBER.fullmatch(answer):
            value = Decimal(answer)
            distractors = [format(value + offset, "f") for offset in (-1, 1, 2, -2)]
            # Do not present numerically equivalent spellings as distractors.
            distractors = [item for item in distractors if Decimal(item) != value]
        else:
            distractors = sorted({word.group() for word in WORD.finditer(evidence.text)
                                  if len(word.group()) >= 4 and word.group().lower() not in STOP_WORDS
                                  and normalize(word.group()) != normalize(answer)},
                                 key=lambda word: (digest((quote + word).encode()), word))
        count = {"easy": 2, "medium": 3, "hard": 4}[difficulty]
        # Avoid duplicate normalized options, including case-only differences.
        seen = {normalize(answer)}
        choices = [answer]
        for option in distractors:
            if normalize(option) not in seen:
                choices.append(option)
                seen.add(normalize(option))
            if len(choices) == count + 1:
                break
        if len(choices) < count + 1:
            return None
        options = tuple(sorted(choices, key=lambda word: digest((blank + word).encode())))
    instruction = {"mcq": "Which option completes this source statement exactly?",
                   "short": "Complete this source statement using its exact missing word(s).",
                   "numerical": "Recall the missing numerical value from the source. Enter a number only; units remain in the statement."}[kind]
    if kind == "numerical" and difficulty != "hard":
        places = len(answer.partition(".")[2])
        instruction += f" Hint: the source writes this value with {places} decimal places."
        if difficulty == "easy":
            value = Decimal(answer)
            step = max(Decimal(1), abs(value) / 10)
            instruction += f" It lies strictly between {format(value - step, 'f')} and {format(value + step, 'f')}."
    fact_id = digest(f"{evidence.document_id}:{evidence.location}:{normalize(quote)}".encode())
    identifier = digest(f"{GENERATOR_VERSION}:{evidence.chunk_id}:{start}:{end}:{kind}:{difficulty}".encode())
    return Question(identifier, fact_id, evidence.chunk_id, start, end, left, right,
                    kind, difficulty, instruction + "\n\n" + blank, answer, options, quote)


def verify_question(store, question):
    """Rebuild the entire question/key from current, provenance-checked evidence."""
    if not isinstance(question, Question):
        raise AssessmentError("Invalid question object.")
    evidence = store.resolve_evidence(question.chunk_id)
    expected = _build(evidence, question.sentence_start, question.sentence_end,
                      question.kind, question.difficulty)
    if expected is None or expected != question:
        raise AssessmentError("Question or answer key does not match its verified source transformation.")
    return evidence


def question_pool(store, topic, *, document_ids=(), difficulty="easy", kinds=KINDS):
    if difficulty not in LEVELS or not kinds or any(kind not in KINDS for kind in kinds):
        raise AssessmentError("Select a valid difficulty and at least one question type.")
    if not isinstance(topic, str) or not 1 <= len(topic.strip()) <= 120:
        raise AssessmentError("Enter a topic between 1 and 120 characters.")
    terms = set(store.query_terms(topic)) - STOP_WORDS
    if not terms:
        raise AssessmentError("Enter a specific topic present in your materials.")
    context = retrieve_context(store, topic, document_ids=document_ids,
                               config=ContextConfig(max_passages=12, max_characters=12000))
    questions = []
    for item in context.evidence:
        for start, end in sentences(item.text):
            # A broad OR retrieval match alone does not make a sentence on-topic.
            if not terms.issubset(set(store.query_terms(item.text[start:end]))):
                continue
            for kind in dict.fromkeys(kinds):
                question = _build(item, start, end, kind, difficulty)
                if question:
                    questions.append(question)
    return questions


def grade_answer(store, question, response):
    verify_question(store, question)
    if not isinstance(response, str) or not response.strip() or len(response) > 500:
        raise AssessmentError("Answer every question (at most 500 characters per answer).")
    if question.kind == "mcq":
        if response not in question.options:
            raise AssessmentError("Choose one of the supplied options.")
        correct = response == question.answer
    elif question.kind == "numerical":
        try:
            # Decimal equivalence accepts 9, 9.0 and 9e0, without arbitrary tolerance.
            value = Decimal(response.strip())
            if not value.is_finite() or len(response.strip()) > 80:
                raise InvalidOperation
            correct = value == Decimal(question.answer)
        except (InvalidOperation, ValueError):
            raise AssessmentError("Enter a finite number only, without units or separators.") from None
    else:
        if normalize(response) != normalize(question.answer):
            return Grade("needs_review", None,
                         "Exact source wording did not match. A paraphrase may be valid; no semantic grade or mastery update was made. Compare the source with a teacher.",
                         "unverified_wording")
        correct = True
    if correct:
        return Grade("correct", 1, "Matches the verified source key. This verifies recall, not deeper understanding.", None)
    return Grade("incorrect", 0, "Does not match the source key. Review the cited statement.",
                 "numeric_recall_mismatch" if question.kind == "numerical" else "source_recall_mismatch")
