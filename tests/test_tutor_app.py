from pathlib import Path

from streamlit.testing.v1 import AppTest

from tutortrace import tutor_ui
from tutortrace.providers.llm import InferenceTimeout, ProviderStatus
from test_tutoring import FakeProvider

ROOT = Path(__file__).resolve().parents[1]


def prepare(tmp_path, monkeypatch, provider):
    monkeypatch.setenv("TUTORTRACE_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(tutor_ui, "make_provider", lambda config: provider)
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    next(button for button in app.button if button.label == "Load sample course").click().run()
    return app


def test_tutor_answer_citation_and_existing_search(tmp_path, monkeypatch):
    app = prepare(tmp_path, monkeypatch, FakeProvider())
    app.text_area(key="tutor_question").set_value("kinetic")
    next(button for button in app.button if button.label == "Ask AI tutor").click().run()
    assert not app.exception and not app.error
    assert any("validated source" in item.value for item in app.success)
    assert any("energy_notes.pdf, page 1" in item.value for item in app.text)
    assert any("not semantic correctness" in item.value for item in app.caption)
    app.text_input[0].set_value("watts")
    next(button for button in app.button if button.label == "Find evidence").click().run()
    assert any("energy_slides.pptx, slide 2" in item.value for item in app.text)
    assert not app.exception


def test_tutor_timeout_recovery_and_status(tmp_path, monkeypatch):
    provider = FakeProvider(error=InferenceTimeout("timeout test"))
    provider.status = lambda: ProviderStatus(False, "Model unavailable")
    app = prepare(tmp_path, monkeypatch, provider)
    next(button for button in app.button if button.label == "Check model status").click().run()
    assert any("Model unavailable" in item.value for item in app.warning)
    app.text_area(key="tutor_question").set_value("kinetic")
    next(button for button in app.button if button.label == "Ask AI tutor").click().run()
    assert not app.exception and any("timeout test" in item.value for item in app.error)
    assert any("No AI answer has been accepted" in item.value for item in app.info)
    provider.error = None
    next(button for button in app.button if button.label == "Ask AI tutor").click().run()
    assert not app.error and not app.exception
    assert any("validated source" in item.value for item in app.success)


def test_tutor_empty_question_and_empty_retrieval(tmp_path, monkeypatch):
    provider = FakeProvider()
    monkeypatch.setenv("TUTORTRACE_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(tutor_ui, "make_provider", lambda config: provider)
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    next(button for button in app.button if button.label == "Ask AI tutor").click().run()
    assert any("Enter a question" in item.value for item in app.error)
    app.text_area(key="tutor_question").set_value("unknown topic")
    next(button for button in app.button if button.label == "Ask AI tutor").click().run()
    assert not app.exception and not app.error and provider.calls == 0
    assert any("no AI inference" in item.value for item in app.caption)
