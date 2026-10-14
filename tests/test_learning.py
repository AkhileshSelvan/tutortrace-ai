from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import sqlite3

import pytest

from scripts.create_demo_assets import make_pdf, make_pptx
from tutortrace.assessment import (AssessmentError, Question, grade_answer,
                                  question_pool, verify_question)
from tutortrace.errors import ProvenanceError, StorageError
from tutortrace.ingestion.service import ingest
from tutortrace.learning import LearningStore, adapted_difficulty, mastery_score, recommendations
from tutortrace.persistence import Store
from tutortrace import models


@pytest.fixture
def course(store, tmp_path):
    slides = tuple(f"Energy example {i} describes a moving object. Energy measured in this experiment is {i * 10} joules."
                   for i in range(1, 10)) + (
        "Energy requires understanding mass and speed. Energy is conserved in an isolated system.",
        "Power is the rate of energy transfer. Power in this experiment is 20 watts.",
    )
    doc = ingest(store, "physics.pptx", make_pptx(slides)).document
    learning = LearningStore(tmp_path / "progress.sqlite3")
    learner = learning.create_learner("Student")
    return store, learning, learner, doc.id


def start(course, **kwargs):
    source, learning, learner, doc = course
    sid = learning.begin(source, learner, "energy", document_ids=(doc,), **kwargs)
    return learning.session(learner, sid)


def complete(course, session, correct=True):
    source, learning, learner, _ = course
    answers = {q.id: q.answer if correct else next(option for option in q.options if option != q.answer)
               for q in session["questions"]}
    return learning.submit(source, learner, session["id"], answers)


@pytest.mark.parametrize("kind", ["mcq", "short", "numerical"])
def test_question_types_have_verified_keys_and_slide_locations(course, kind):
    source, _, _, doc = course
    pool = question_pool(source, "energy", document_ids=(doc,), kinds=(kind,))
    assert pool
    for question in pool:
        evidence = verify_question(source, question)
        assert evidence.document_id == doc and evidence.location >= 1
        assert "slide" in evidence.citation
        assert question.quote in evidence.text
        assert question.answer == evidence.text[question.answer_start:question.answer_end]
        assert grade_answer(source, question, question.answer).score == 1


@pytest.mark.parametrize("field,value", [
    ("answer", "invented"), ("prompt", "What is the capital of Mars?"),
    ("quote", "Fabricated source"), ("id", "invented"),
    ("fact_id", "invented"), ("answer_start", 0), ("options", ("fake", "false")),
    ("difficulty", "impossible"), ("sentence_end", 1),
])
def test_question_and_key_tampering_rejected(course, field, value):
    source = course[0]
    question = question_pool(source, "energy", kinds=("mcq",))[0]
    with pytest.raises(AssessmentError):
        verify_question(source, replace(question, **{field: value}))


def test_pdf_physical_page_and_label(store):
    import pymupdf
    with pymupdf.open(stream=make_pdf(("", "Energy in the moving object is 9 joules.")), filetype="pdf") as pdf:
        pdf.set_page_labels([{"startpage": 0, "prefix": "", "style": "r", "firstpagenum": 1},
                             {"startpage": 1, "prefix": "", "style": "D", "firstpagenum": 1}])
        content = pdf.tobytes()
    ingest(store, "lesson.pdf", content)
    question = question_pool(store, "energy", kinds=("numerical",))[0]
    evidence = verify_question(store, question)
    assert evidence.location == 2 and evidence.page_label == "1"
    assert "PDF page 2 (label: 1)" in evidence.citation


def test_no_unsupported_or_empty_topic_questions(course):
    assert question_pool(course[0], "quantum biology") == []
    with pytest.raises(AssessmentError):
        course[1].begin(course[0], course[2], "quantum biology")
    assert course[1].dashboard(course[2]) == []
    for topic in ("", "the and", "x" * 121):
        with pytest.raises(AssessmentError):
            question_pool(course[0], topic)


def test_document_isolation_and_topic_scope(course):
    source, learning, learner, doc = course
    other = ingest(source, "other.pptx", make_pptx(("Energy in another course is measured as 999 joules.",))).document
    pool = question_pool(source, "energy", document_ids=(doc,))
    assert all(verify_question(source, q).document_id == doc for q in pool)
    a = learning.topic(source, "Energy", (doc,))
    b = learning.topic(source, "energy", (other.id,))
    assert a["id"] != b["id"]
    assert a["id"] == learning.topic(source, "ENERGY", (doc, doc))["id"]


def test_no_fact_repetition_across_formats_and_difficulty(course):
    first = start(course, count=3, kinds=("mcq",))
    complete(course, first)
    second = start(course, count=3, kinds=("short",), difficulty="hard")
    assert not {q.fact_id for q in first["questions"]} & {q.fact_id for q in second["questions"]}
    assert len({q.fact_id for q in second["questions"]}) == len(second["questions"])


def test_abandon_does_not_update_mastery_or_allow_immediate_repeat(course):
    source, learning, learner, _ = course
    first = start(course, count=3)
    learning.abandon(learner, first["id"])
    assert learning.history(learner) == []
    second = start(course, count=3)
    assert not {q.fact_id for q in first["questions"]} & {q.fact_id for q in second["questions"]}


def test_pool_exhaustion_fails_without_duplicate_or_partial_session(store, tmp_path):
    ingest(store, "one.pptx", make_pptx(("Energy of the object is 9 joules.",)))
    learning = LearningStore(tmp_path / "learning.sqlite3")
    learner = learning.create_learner("One")
    sid = learning.begin(store, learner, "energy", kinds=("numerical",), count=8)
    session = learning.session(learner, sid)
    assert len(session["questions"]) == 1
    learning.submit(store, learner, sid, {q.id: q.answer for q in session["questions"]})
    with pytest.raises(AssessmentError, match="No new"):
        learning.begin(store, learner, "energy", kinds=("mcq",))
    assert learning.session(learner)["id"] == sid


def test_student_isolation_and_empty_history(course):
    source, learning, learner, _ = course
    other = learning.create_learner("Other")
    assert learning.history(other) == [] and learning.dashboard(other) == [] and learning.session(other) is None
    first = start(course, count=2, kinds=("mcq",))
    with pytest.raises(AssessmentError):
        learning.session(other, first["id"])
    with pytest.raises(AssessmentError):
        learning.submit(source, other, first["id"], {q.id: q.answer for q in first["questions"]})
    with pytest.raises(AssessmentError):
        learning.abandon(other, first["id"])
    complete(course, first)
    assert learning.dashboard(other) == []
    second = learning.begin(source, other, "energy", document_ids=(course[3],), kinds=("mcq",), count=2)
    assert [q.id for q in learning.session(other, second)["questions"]] == [q.id for q in first["questions"]]


def test_mastery_formula_diagnostic_and_adaptation(course):
    _, learning, learner, _ = course
    assert mastery_score(0, 0) == 0.5
    assert mastery_score(3, 1) == pytest.approx(4 / 6)
    assert adapted_difficulty(0, 0) == "easy"
    assert adapted_difficulty(0, 2) == "easy"
    assert adapted_difficulty(2, 1) == "medium"
    assert adapted_difficulty(3, 0) == "hard"
    first = start(course, count=3, kinds=("mcq",))
    assert first["diagnostic"] == 1 and first["difficulty"] == "easy"
    complete(course, first)
    row = learning.dashboard(learner)[0]
    assert row["score"] == 0.8 and row["correct"] == 3
    second = start(course, count=2, kinds=("mcq",))
    assert second["difficulty"] == "hard" and not second["diagnostic"]
    complete(course, second, correct=False)
    row = learning.dashboard(learner)[0]
    assert row["score"] == pytest.approx(4 / 7) and row["next_difficulty"] == "medium"


def test_short_answer_paraphrase_is_ungraded_not_wrong(course):
    source, learning, learner, _ = course
    session = start(course, count=1, kinds=("short",))
    result = learning.submit(source, learner, session["id"], {session["questions"][0].id: "a possible paraphrase"})
    attempt = result["attempts"][0]
    assert attempt["score"] is None and attempt["status"] == "needs_review"
    assert attempt["mastery_before"] == attempt["mastery_after"] == 0.5
    assert learning.dashboard(learner)[0]["review"] == 1


def test_short_answer_normalization_and_numerical_grading(course):
    source = course[0]
    short = question_pool(source, "energy", kinds=("short",))[0]
    assert grade_answer(source, short, "  " + short.answer.upper() + "  ").score == 1
    number = question_pool(source, "energy", kinds=("numerical",))[0]
    assert grade_answer(source, number, number.answer + ".0").score == 1
    assert grade_answer(source, number, "987654321").score == 0
    for response in ("NaN", "Infinity", "ten", "9 joules", "", None):
        with pytest.raises(AssessmentError):
            grade_answer(source, number, response)


def test_mcq_invalid_option_rejected(course):
    question = question_pool(course[0], "energy", kinds=("mcq",))[0]
    with pytest.raises(AssessmentError):
        grade_answer(course[0], question, "invented option")


def test_restart_preserves_open_quiz_grades_and_source_schema(course):
    source, learning, learner, _ = course
    with source.connection() as conn:
        before = list(conn.iterdump())
    session = start(course, count=3, kinds=("mcq",))
    restarted = LearningStore(learning.path)
    assert restarted.session(learner)["questions"] == session["questions"]
    complete((Store(source.path), restarted, learner, course[3]), session)
    assert LearningStore(learning.path).dashboard(learner)[0]["correct"] == 3
    assert len(LearningStore(learning.path).history(learner)) == 3
    with source.connection() as conn:
        assert list(conn.iterdump()) == before
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 2


def test_invalid_response_rolls_back_entire_submission(course):
    source, learning, learner, _ = course
    session = start(course, count=3, kinds=("mcq",))
    answers = {q.id: q.answer for q in session["questions"]}
    answers[session["questions"][-1].id] = "invalid"
    with pytest.raises(AssessmentError):
        learning.submit(source, learner, session["id"], answers)
    assert learning.history(learner) == []
    assert learning.session(learner)["status"] == "open"
    assert learning.dashboard(learner)[0]["score"] == 0.5


def test_database_failure_rolls_back_attempts_mastery_and_completion(course):
    source, learning, learner, _ = course
    session = start(course, count=3, kinds=("mcq",))
    with learning.connection() as conn:
        conn.execute("CREATE TRIGGER fail_completion BEFORE UPDATE OF status ON sessions BEGIN SELECT RAISE(ABORT,'injected failure'); END")
    with pytest.raises(StorageError):
        complete(course, session)
    assert learning.history(learner) == []
    assert learning.dashboard(learner)[0]["correct"] == 0
    assert learning.session(learner)["status"] == "open"
    with learning.connection() as conn:
        conn.execute("DROP TRIGGER fail_completion")
    complete(course, session)
    assert len(learning.history(learner)) == 3


def test_double_submission_and_concurrent_submission_are_safe(course):
    session = start(course, count=2, kinds=("mcq",))
    def submit():
        try:
            complete(course, session)
            return "completed"
        except AssessmentError:
            return "closed"
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(lambda _: submit(), range(2))) == ["closed", "completed"]
    assert len(course[1].history(course[2])) == 2


def test_only_one_open_assessment_per_learner(course):
    first = start(course)
    with pytest.raises(AssessmentError, match="Finish or abandon"):
        start(course)
    assert course[1].session(course[2])["id"] == first["id"]


def test_corrupt_evidence_blocks_grading(course):
    source, learning, learner, _ = course
    session = start(course, count=1)
    with source.connection() as conn:
        conn.execute("UPDATE chunks SET text='corrupt' WHERE id=?", (session["questions"][0].chunk_id,))
    with pytest.raises(ProvenanceError):
        complete(course, session)
    assert learning.history(learner) == []


def test_cached_answer_corruption_blocks_grading(course):
    source, learning, learner, _ = course
    session = start(course, count=1)
    question = session["questions"][0]
    with learning.connection() as conn:
        conn.execute("UPDATE questions SET payload=? WHERE id=?", (replace(question, answer="fake").to_json(), question.id))
    with pytest.raises(AssessmentError):
        complete(course, session)
    assert learning.history(learner) == []


def test_recommendations_and_explicit_prerequisites(course):
    source, learning, learner, doc = course
    first = start(course, count=2, kinds=("mcq",))
    complete(course, first, correct=False)
    sid = learning.begin(source, learner, "power", document_ids=(doc,), kinds=("mcq",), count=1)
    complete(course, learning.session(learner, sid))
    recs = recommendations(source, learning, learner)
    assert recs[0]["topic"]["label"] == "energy"
    assert "2 objectively graded" in recs[0]["reason"]
    assert recs[0]["evidence"]
    assert recs[0]["foundations"]
    for rec in recs:
        for evidence in rec["evidence"]:
            assert source.resolve_evidence(evidence.chunk_id).text == evidence.text
        for foundation in rec["foundations"]:
            assert foundation["statement"] in foundation["evidence"].text


def test_schema_startup_idempotent_and_rejects_unknown(tmp_path):
    path = tmp_path / "learner.sqlite3"
    first = LearningStore(path)
    identifier = first.create_learner("Stable")
    assert LearningStore(path).learners()[0]["id"] == identifier
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA user_version=999")
    with pytest.raises(StorageError, match="Unsupported"):
        LearningStore(path)
    other = tmp_path / "unknown.sqlite3"
    with sqlite3.connect(other) as conn:
        conn.execute("CREATE TABLE private_data (value TEXT)")
    with pytest.raises(StorageError, match="unknown"):
        LearningStore(other)
    with sqlite3.connect(other) as conn:
        assert conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == [("private_data",)]


def test_malformed_cached_question_rejected():
    for payload in ('{}', 'null', '[]', 'not json'):
        with pytest.raises(AssessmentError):
            Question.from_json(payload)


def test_pipeline_upgrade_retires_questions_but_retains_learning_history(course, monkeypatch):
    source, learning, learner, doc = course
    session = start(course, count=1, kinds=("mcq",))
    complete(course, session)
    old = session["questions"][0]
    monkeypatch.setattr(models, "PIPELINE_VERSION", "assessment-reindex-regression")
    # Merely changing the current version does not invalidate persisted evidence.
    verify_question(source, old)
    result = ingest(source, "physics.pptx", source.original(doc))
    assert result.reindexed
    with pytest.raises(ProvenanceError):
        verify_question(source, old)
    assert len(learning.history(learner)) == 1
    assert learning.dashboard(learner)[0]["correct"] == 1
    fresh = start(course, count=1, kinds=("mcq",))
    assert fresh["questions"][0].chunk_id != old.chunk_id
    verify_question(source, fresh["questions"][0])


def test_valid_question_cannot_replace_another_assigned_identity(course):
    source, learning, learner, _ = course
    session = start(course, count=1, kinds=("mcq",))
    assigned = session["questions"][0]
    other = next(q for q in question_pool(source, "energy", kinds=("mcq",)) if q.id != assigned.id)
    with learning.connection() as conn:
        conn.execute("UPDATE questions SET payload=? WHERE id=?", (other.to_json(), assigned.id))
    with pytest.raises(AssessmentError, match="identity"):
        learning.submit(source, learner, session["id"], {other.id: other.answer})
    assert learning.history(learner) == []


def test_request_limits_and_unknown_learner_fail_without_changes(course):
    source, learning, learner, _ = course
    for count in (0, 9, True):
        with pytest.raises(AssessmentError):
            learning.begin(source, learner, "energy", count=count)
    with pytest.raises(AssessmentError):
        learning.begin(source, "unknown", "energy")
    with pytest.raises(AssessmentError):
        learning.begin(source, learner, "energy", kinds=())
    assert learning.session(learner) is None


def test_numerical_mcq_options_are_distinct_values(course):
    from decimal import Decimal
    source = course[0]
    questions = [q for q in question_pool(source, "energy", kinds=("mcq",)) if q.answer.isdigit()]
    assert questions
    for question in questions:
        assert len({Decimal(option) for option in question.options}) == len(question.options)
        assert sum(grade_answer(source, question, option).score for option in question.options) == 1


def test_generation_failure_rolls_back_topic_mastery_and_session(course):
    source, learning, learner, _ = course
    with learning.connection() as conn:
        conn.execute("CREATE TRIGGER fail_question BEFORE INSERT ON session_questions BEGIN SELECT RAISE(ABORT,'injected'); END")
    with pytest.raises(StorageError):
        start(course)
    assert learning.dashboard(learner) == []
    assert learning.session(learner) is None
    with learning.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM topics").fetchone()[0] == 0


def test_unseen_facts_preferred_after_cooldown(course):
    source, learning, learner, _ = course
    seen = set()
    for _ in range(4):
        session = start(course, kinds=("mcq",), count=2)
        facts = {q.fact_id for q in session["questions"]}
        assert not facts & seen
        seen.update(facts)
        complete(course, session)


def test_nonnumeric_source_never_creates_numerical_key(store):
    ingest(store, "words.pptx", make_pptx(("Photosynthesis converts light into chemical energy.",)))
    assert question_pool(store, "photosynthesis", kinds=("numerical",)) == []


def test_difficulty_changes_scaffolding_not_just_metadata(course):
    source = course[0]
    numerical = [question_pool(source, "energy", kinds=("numerical",), difficulty=level)[0]
                 for level in ("easy", "medium", "hard")]
    assert len({q.prompt for q in numerical}) == 3
    assert len({q.fact_id for q in numerical}) == 1
    assert "strictly between" in numerical[0].prompt
    assert "decimal places" in numerical[1].prompt
    assert "Hint:" not in numerical[2].prompt
    assert [len(question_pool(source, "energy", kinds=("mcq",), difficulty=level)[0].options)
            for level in ("easy", "medium", "hard")] == [3, 4, 5]


def test_simulation_configuration_and_observed_invariants(tmp_path):
    from scripts.evaluate_learning import ROOT, run
    config = json.loads((ROOT / "evaluation/learning_profiles.json").read_text())
    result = run(config, tmp_path)
    assert len(result["profiles"]) == 3
    for profile in result["profiles"]:
        assert profile["sessions_completed"] == profile["sessions_requested"] == 9
        assert profile["questions_completed"] == profile["questions_requested"] == 27
        assert profile["repeated_facts_within_two_sessions"] == profile["repeated_facts_ever"] == 0
        assert profile["restart_preserved"]
    assert result["profiles"][0]["final_mastery"]["kinetic energy"]["estimate"] == pytest.approx(4 / 11)
    assert result["profiles"][1]["recommendation_changes"] > 0
    assert "hard" in result["profiles"][2]["difficulty_sequence"]


def test_unsupported_numeric_notation_is_not_truncated_into_a_key(store):
    ingest(store, "notation.pptx", make_pptx((
        "Energy of the object is −9 joules.",
        "Energy of the other object is 1,000 joules.",
        "Energy in the experiment is 1e3 joules.",
    )))
    assert question_pool(store, "energy", kinds=("numerical",)) == []


def test_signed_decimal_grade_uses_exact_decimal_equivalence(store):
    ingest(store, "decimal.pptx", make_pptx(("Energy change in this example is -9.8 joules.",)))
    question = question_pool(store, "energy", kinds=("numerical",))[0]
    assert question.answer == "-9.8"
    assert grade_answer(store, question, "-9.80").score == 1
    assert grade_answer(store, question, "-9.8001").score == 0


def test_missing_or_extra_submission_answers_do_not_write_partial_history(course):
    source, learning, learner, _ = course
    session = start(course, count=2)
    answers = {q.id: q.answer for q in session["questions"]}
    for invalid in ({}, {**answers, "foreign-question": "answer"}):
        with pytest.raises(AssessmentError):
            learning.submit(source, learner, session["id"], invalid)
        assert learning.history(learner) == []


def test_simulation_rejects_inconsistent_input_configuration(tmp_path):
    from scripts.evaluate_learning import ROOT, run
    config = json.loads((ROOT / "evaluation/learning_profiles.json").read_text())
    config["rounds"] = 4
    with pytest.raises(ValueError, match="inputs"):
        run(config, tmp_path)
