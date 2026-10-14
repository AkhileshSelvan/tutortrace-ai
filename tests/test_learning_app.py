from pathlib import Path

from streamlit.testing.v1 import AppTest

from scripts.create_demo_assets import make_pptx
from tutortrace.learning import LearningStore

ROOT = Path(__file__).resolve().parents[1]


def button(app, label):
    return next(item for item in app.button if item.label == label)


def prepare(tmp_path, monkeypatch):
    monkeypatch.setenv("TUTORTRACE_DATA_DIR", str(tmp_path))
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    content = make_pptx((
        "Energy of the first object is 9 joules. Energy is the capacity to perform work.",
        "Energy of the second object is 20 joules. Energy requires understanding mass and speed.",
        "Energy in an isolated system remains constant. Energy of the final object is 30 joules.",
    ))
    app.file_uploader[0].set_value(("practice.pptx", content, "application/vnd.openxmlformats-officedocument.presentationml.presentation"))
    button(app, "Ingest documents").click().run()
    app.text_input(key="learning_name").set_value("UI Learner")
    button(app, "Create learner").click().run()
    return app, LearningStore(tmp_path / "tutortrace.learning.sqlite3")


def test_complete_assessment_dashboard_revision_and_restart(tmp_path, monkeypatch):
    app, learning = prepare(tmp_path, monkeypatch)
    assert not app.exception
    assert any("No learning history" in item.value for item in app.caption)
    learner = learning.learners()[0]["id"]
    button(app, "Generate assessment").click().run()
    assert not app.exception
    session = learning.session(learner)
    assert session["diagnostic"]
    assert not any("Verified source key" in item.value for item in app.text)
    for question in session["questions"]:
        key = f"answer_{session['id']}_{question.id}"
        if question.kind == "mcq":
            app.radio(key=key).set_value(question.answer)
        else:
            app.text_input(key=key).set_value(question.answer)
    button(app, "Grade assessment").click().run()
    assert not app.exception and not app.error
    assert learning.dashboard(learner)[0]["correct"] == len(session["questions"])
    assert any("Verified source key" in item.value for item in app.text)
    assert any("practice.pptx, slide" in item.value for item in app.text)
    button(app, "Revise with AI tutor").click().run()
    assert not app.exception
    assert "Help me revise energy" in app.text_area(key="tutor_question").value
    assert app.multiselect(key="tutor_scope").value
    restarted = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not restarted.exception
    assert any("Verified source key" in item.value for item in restarted.text)
    assert len(learning.history(learner)) == len(session["questions"])


def test_quiz_validation_and_profile_isolation(tmp_path, monkeypatch):
    app, learning = prepare(tmp_path, monkeypatch)
    button(app, "Generate assessment").click().run()
    button(app, "Grade assessment").click().run()
    assert not app.exception
    assert any("Answer every question" in item.value for item in app.warning)
    learner = learning.learners()[0]["id"]
    assert learning.history(learner) == []
    app.text_input(key="learning_name").set_value("Second learner")
    button(app, "Create learner").click().run()
    assert not app.exception
    assert learning.learners()[1]["id"] == app.selectbox(key="learning_learner").value
    assert any("No learning history" in item.value for item in app.caption)
    assert not any("Grade assessment" == item.label for item in app.button)
