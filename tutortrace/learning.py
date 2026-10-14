"""Local learner history, atomic assessments and transparent Beta-count mastery.

This sidecar never migrates or writes the source ledger. A source key is checked
again at issue, grading and recommendation time, including after re-indexing.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
from uuid import uuid4

from tutortrace.assessment import (AssessmentError, KINDS, LEVELS, Question,
                                  grade_answer, normalize, question_pool, verify_question)
from tutortrace.errors import StorageError
from tutortrace.models import digest
from tutortrace.retrieval.context import retrieve_context
from tutortrace.retrieval.search import STOP_WORDS

SCHEMA_VERSION = 1
SCHEMA = (
    "CREATE TABLE learners (id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL)",
    "CREATE TABLE topics (id TEXT PRIMARY KEY, label TEXT NOT NULL, document_ids TEXT NOT NULL)",
    "CREATE TABLE questions (id TEXT PRIMARY KEY, payload TEXT NOT NULL)",
    """CREATE TABLE sessions (id TEXT PRIMARY KEY, learner_id TEXT NOT NULL REFERENCES learners(id),
       topic_id TEXT NOT NULL REFERENCES topics(id), difficulty TEXT NOT NULL,
       diagnostic INTEGER NOT NULL, status TEXT NOT NULL CHECK(status IN ('open','completed','abandoned')),
       created_at TEXT NOT NULL, completed_at TEXT)""",
    "CREATE UNIQUE INDEX one_open_session ON sessions(learner_id) WHERE status='open'",
    """CREATE TABLE session_questions (session_id TEXT NOT NULL REFERENCES sessions(id),
       position INTEGER NOT NULL, question_id TEXT NOT NULL REFERENCES questions(id),
       fact_id TEXT NOT NULL, PRIMARY KEY(session_id, position), UNIQUE(session_id, fact_id))""",
    """CREATE TABLE attempts (id INTEGER PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
       question_id TEXT NOT NULL REFERENCES questions(id), response TEXT NOT NULL,
       status TEXT NOT NULL CHECK(status IN ('correct','incorrect','needs_review')),
       score INTEGER CHECK(score IN (0,1)), feedback TEXT NOT NULL, misconception TEXT,
       mastery_before REAL NOT NULL, mastery_after REAL NOT NULL, created_at TEXT NOT NULL,
       UNIQUE(session_id, question_id))""",
    """CREATE TABLE mastery (learner_id TEXT NOT NULL REFERENCES learners(id),
       topic_id TEXT NOT NULL REFERENCES topics(id), correct INTEGER NOT NULL DEFAULT 0 CHECK(correct>=0),
       incorrect INTEGER NOT NULL DEFAULT 0 CHECK(incorrect>=0), review INTEGER NOT NULL DEFAULT 0 CHECK(review>=0),
       PRIMARY KEY(learner_id, topic_id))""",
)


def now():
    return datetime.now(timezone.utc).isoformat()


def mastery_score(correct, incorrect):
    """Beta(1,1) posterior mean of source-recall success, not calibrated knowledge."""
    return (1 + correct) / (2 + correct + incorrect)


def adapted_difficulty(correct, incorrect):
    if correct + incorrect == 0:
        return "easy"
    score = mastery_score(correct, incorrect)
    return "easy" if score < 0.45 else "hard" if score >= 0.75 and correct + incorrect >= 3 else "medium"


class LearningStore:
    def __init__(self, path):
        self.path = Path(path).resolve()
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.connection() as conn:
                conn.execute("BEGIN IMMEDIATE")
                version = conn.execute("PRAGMA user_version").fetchone()[0]
                if version not in (0, SCHEMA_VERSION):
                    raise StorageError("Unsupported learner database version.")
                if version == 0:
                    if conn.execute("SELECT 1 FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' LIMIT 1").fetchone():
                        raise StorageError("Refusing to overwrite an unknown learner database.")
                    for statement in SCHEMA:
                        conn.execute(statement)
                    conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        except OSError as exc:
            raise StorageError("Could not open the learner data directory.") from exc

    @contextmanager
    def connection(self):
        conn = None
        try:
            conn = sqlite3.connect(self.path, timeout=15)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            with conn:
                yield conn
        except sqlite3.Error as exc:
            raise StorageError("Learner database operation failed; changes were rolled back.") from exc
        finally:
            if conn is not None:
                conn.close()

    def create_learner(self, name):
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
            raise AssessmentError("Enter a learner name between 1 and 80 characters.")
        identifier = uuid4().hex
        with self.connection() as conn:
            conn.execute("INSERT INTO learners VALUES (?,?,?)", (identifier, name.strip(), now()))
        return identifier

    def learners(self):
        with self.connection() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM learners ORDER BY created_at,id")]

    @staticmethod
    def _learner(conn, learner_id):
        if not conn.execute("SELECT 1 FROM learners WHERE id=?", (learner_id,)).fetchone():
            raise AssessmentError("Select an existing learner.")

    def topic(self, source, label, document_ids=()):
        if not isinstance(label, str) or not 1 <= len(label.strip()) <= 120:
            raise AssessmentError("Enter a topic between 1 and 120 characters.")
        scopes = tuple(sorted(set(document_ids or [doc.id for doc in source.list_documents()])))
        if not scopes or len(scopes) > 50 or any(source.get_document(value) is None for value in scopes):
            raise AssessmentError("Select between 1 and 50 existing documents.")
        terms = sorted(set(source.query_terms(label)) - STOP_WORDS)
        if not terms:
            raise AssessmentError("Enter a specific topic present in your materials.")
        identifier = digest(json.dumps([terms, scopes]).encode())
        return {"id": identifier, "label": label.strip(), "document_ids": json.dumps(scopes)}

    def begin(self, source, learner_id, label, *, document_ids=(), difficulty="adaptive", kinds=KINDS, count=3):
        if type(count) is not int or not 1 <= count <= 8 or difficulty not in (*LEVELS, "adaptive"):
            raise AssessmentError("Choose 1–8 questions and a valid difficulty.")
        topic = self.topic(source, label, document_ids)
        with self.connection() as conn:
            # Serialize selection with submission/other tabs to enforce no-repeat
            # and exactly one unfinished assessment per learner.
            conn.execute("BEGIN IMMEDIATE")
            self._learner(conn, learner_id)
            if conn.execute("SELECT 1 FROM sessions WHERE learner_id=? AND status='open'", (learner_id,)).fetchone():
                raise AssessmentError("Finish or abandon the current assessment first.")
            row = conn.execute("SELECT * FROM mastery WHERE learner_id=? AND topic_id=?", (learner_id, topic["id"])).fetchone()
            correct, incorrect = (row["correct"], row["incorrect"]) if row else (0, 0)
            level = adapted_difficulty(correct, incorrect) if difficulty == "adaptive" else difficulty
            candidates = question_pool(source, label, document_ids=tuple(json.loads(topic["document_ids"])), difficulty=level, kinds=kinds)
            # Last two issued sessions, including abandoned ones, plus within-quiz
            # deduplication. This is fact-based across type and difficulty changes.
            recent = conn.execute("SELECT id FROM sessions WHERE learner_id=? ORDER BY created_at DESC,id DESC LIMIT 2", (learner_id,)).fetchall()
            excluded = set()
            for previous in recent:
                excluded.update(row[0] for row in conn.execute("SELECT fact_id FROM session_questions WHERE session_id=?", (previous[0],)))
            exposures = dict(conn.execute("""SELECT sq.fact_id,COUNT(*) FROM session_questions sq
                JOIN sessions s ON s.id=sq.session_id WHERE s.learner_id=? GROUP BY sq.fact_id""", (learner_id,)))
            chosen = []
            requested_kinds = tuple(dict.fromkeys(kinds))
            # Rotate types so mixed quizzes use different formats where the source
            # supports them, without manufacturing extra facts to fill a count.
            while len(chosen) < count:
                preferred = requested_kinds[len(chosen) % len(requested_kinds)]
                available = [q for q in candidates if q.fact_id not in excluded]
                if not available:
                    break
                # Prefer unseen facts, then the least exposed eligible facts.
                # A finite corpus can be revised again after the hard cooldown.
                least_seen = min(exposures.get(q.fact_id, 0) for q in available)
                available = [q for q in available if exposures.get(q.fact_id, 0) == least_seen]
                question = next((q for q in available if q.kind == preferred), available[0])
                verify_question(source, question)
                chosen.append(question)
                excluded.add(question.fact_id)
            if not chosen:
                raise AssessmentError("No new verifiable questions for this topic and format. Recent facts are withheld; choose another topic, add material, or resume an existing quiz.")
            conn.execute("INSERT OR IGNORE INTO topics VALUES (?,?,?)", (topic["id"], topic["label"], topic["document_ids"]))
            conn.execute("INSERT OR IGNORE INTO mastery(learner_id,topic_id) VALUES (?,?)", (learner_id, topic["id"]))
            session_id = uuid4().hex
            conn.execute("INSERT INTO sessions VALUES (?,?,?,?,?,'open',?,NULL)",
                         (session_id, learner_id, topic["id"], level, int(correct + incorrect == 0), now()))
            for position, question in enumerate(chosen):
                cached = conn.execute("SELECT payload FROM questions WHERE id=?", (question.id,)).fetchone()
                if cached and Question.from_json(cached[0]) != question:
                    raise AssessmentError("Cached question failed integrity verification.")
                conn.execute("INSERT OR IGNORE INTO questions VALUES (?,?)", (question.id, question.to_json()))
                conn.execute("INSERT INTO session_questions VALUES (?,?,?,?)", (session_id, position, question.id, question.fact_id))
            return session_id

    def session(self, learner_id, session_id=None):
        with self.connection() as conn:
            self._learner(conn, learner_id)
            if session_id is None:
                row = conn.execute("SELECT * FROM sessions WHERE learner_id=? ORDER BY created_at DESC,id DESC LIMIT 1", (learner_id,)).fetchone()
            else:
                row = conn.execute("SELECT * FROM sessions WHERE id=? AND learner_id=?", (session_id, learner_id)).fetchone()
            if row is None:
                if session_id is not None:
                    raise AssessmentError("Assessment does not belong to this learner.")
                return None
            result = dict(row)
            result["topic"] = dict(conn.execute("SELECT * FROM topics WHERE id=?", (row["topic_id"],)).fetchone())
            result["questions"] = self._questions(conn, row["id"])
            result["attempts"] = [dict(item) for item in conn.execute("SELECT * FROM attempts WHERE session_id=? ORDER BY id", (row["id"],))]
            return result

    @staticmethod
    def _questions(conn, session_id):
        questions = []
        for row in conn.execute("""SELECT q.id,q.payload,sq.fact_id FROM session_questions sq
                JOIN questions q ON q.id=sq.question_id WHERE sq.session_id=? ORDER BY sq.position""", (session_id,)):
            question = Question.from_json(row["payload"])
            if question.id != row["id"] or question.fact_id != row["fact_id"]:
                raise AssessmentError("Stored assessment identity does not match its assigned question.")
            questions.append(question)
        if not questions:
            raise AssessmentError("Stored assessment has no questions.")
        return questions

    def submit(self, source, learner_id, session_id, responses):
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            session = conn.execute("SELECT * FROM sessions WHERE id=? AND learner_id=?", (session_id, learner_id)).fetchone()
            if session is None:
                raise AssessmentError("Assessment does not belong to this learner.")
            if session["status"] != "open":
                raise AssessmentError("Assessment is already closed; grades cannot be submitted twice.")
            questions = self._questions(conn, session_id)
            if not isinstance(responses, dict) or set(responses) != {q.id for q in questions}:
                raise AssessmentError("Submit exactly one answer for every assigned question.")
            # Validate all responses before writing even the first attempt.
            grades = [grade_answer(source, q, responses[q.id]) for q in questions]
            mastery = conn.execute("SELECT * FROM mastery WHERE learner_id=? AND topic_id=?", (learner_id, session["topic_id"])).fetchone()
            correct, incorrect, review = mastery["correct"], mastery["incorrect"], mastery["review"]
            for question, grade in zip(questions, grades, strict=True):
                before = mastery_score(correct, incorrect)
                correct += grade.score == 1
                incorrect += grade.score == 0
                review += grade.score is None
                after = mastery_score(correct, incorrect)
                conn.execute("INSERT INTO attempts(session_id,question_id,response,status,score,feedback,misconception,mastery_before,mastery_after,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                             (session_id, question.id, responses[question.id], grade.status, grade.score, grade.feedback,
                              grade.misconception, before, after, now()))
            conn.execute("UPDATE mastery SET correct=?,incorrect=?,review=? WHERE learner_id=? AND topic_id=?",
                         (correct, incorrect, review, learner_id, session["topic_id"]))
            conn.execute("UPDATE sessions SET status='completed',completed_at=? WHERE id=?", (now(), session_id))
        return self.session(learner_id, session_id)

    def abandon(self, learner_id, session_id):
        with self.connection() as conn:
            result = conn.execute("UPDATE sessions SET status='abandoned',completed_at=? WHERE id=? AND learner_id=? AND status='open'", (now(), session_id, learner_id))
            if result.rowcount != 1:
                raise AssessmentError("No open assessment belongs to this learner.")

    def dashboard(self, learner_id):
        with self.connection() as conn:
            self._learner(conn, learner_id)
            rows = [dict(row) for row in conn.execute("SELECT m.*,t.label,t.document_ids FROM mastery m JOIN topics t ON t.id=m.topic_id WHERE learner_id=?", (learner_id,))]
        for row in rows:
            row["score"] = mastery_score(row["correct"], row["incorrect"])
            row["verified_attempts"] = row["correct"] + row["incorrect"]
            row["next_difficulty"] = adapted_difficulty(row["correct"], row["incorrect"])
        return sorted(rows, key=lambda row: (row["score"], row["verified_attempts"], row["label"], row["topic_id"]))

    def history(self, learner_id):
        with self.connection() as conn:
            self._learner(conn, learner_id)
            return [dict(row) for row in conn.execute("""SELECT a.*,s.topic_id,s.difficulty,s.diagnostic,t.label FROM attempts a
                JOIN sessions s ON s.id=a.session_id JOIN topics t ON t.id=s.topic_id
                WHERE s.learner_id=? ORDER BY a.id""", (learner_id,))]

    def sessions(self, learner_id):
        with self.connection() as conn:
            self._learner(conn, learner_id)
            return [dict(row) for row in conn.execute("""SELECT s.*,t.label FROM sessions s
                JOIN topics t ON t.id=s.topic_id WHERE learner_id=? ORDER BY s.created_at DESC,s.id DESC""", (learner_id,))]


def recommendations(source, learning, learner_id, limit=3):
    results = []
    for topic in learning.dashboard(learner_id)[:limit]:
        context = retrieve_context(source, topic["label"], document_ids=tuple(json.loads(topic["document_ids"])))
        terms = set(source.query_terms(topic["label"])) - STOP_WORDS
        evidence = tuple(item for item in context.evidence if terms.issubset(set(source.query_terms(item.text))))
        n = topic["verified_attempts"]
        reason = ("No objectively graded answers yet; complete a diagnostic." if not n else
                  f"Source-recall estimate {topic['score']:.0%} from {n} objectively graded answers; weaker tracked topics are prioritized.")
        foundations = []
        # Only explicit prerequisite language in the source is eligible. No
        # inferred curriculum graph, and absence is shown as unknown.
        for item in evidence:
            for match in re.finditer(r"[^.!?\n]*(?:requires understanding|prerequisite is|prerequisites are) [^.!?\n]+[.!?]?", item.text, re.I):
                if terms.issubset(set(source.query_terms(match.group()))):
                    foundations.append({"statement": match.group().strip(), "evidence": item})
        results.append({"topic": topic, "reason": reason, "evidence": evidence, "foundations": foundations})
    return results


def revision_request(recommendation):
    """A learner-aware prompt; the unchanged tutor still controls evidence/claims."""
    topic = recommendation["topic"]
    return (
        f"Help me revise {topic['label']}. My source-recall practice level is {topic['next_difficulty']}. "
        "Explain the key ideas using only the selected material, and mention prerequisites only if the sources explicitly state them.",
        tuple(json.loads(topic["document_ids"])),
    )
