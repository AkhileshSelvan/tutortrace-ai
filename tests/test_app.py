from pathlib import Path

from streamlit.testing.v1 import AppTest

from tutortrace.persistence import Store

ROOT = Path(__file__).resolve().parents[1]


def test_streamlit_sample_search_inspection_and_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("TUTORTRACE_DATA_DIR", str(tmp_path))
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not app.exception
    next(button for button in app.button if button.label == "Load sample course").click().run()
    assert not app.exception
    assert len(Store(tmp_path / "tutortrace.sqlite3").list_documents()) == 2
    app.text_input[0].set_value("watts")
    next(button for button in app.button if button.label == "Find evidence").click().run()
    assert not app.exception
    assert any("energy_slides.pptx, slide 2" in text.value for text in app.text)
    assert any("20 watts" in text.value for text in app.text)
    assert any("Chunk ID:" in text.value for text in app.text)
    # A separate app session uses the existing index without re-ingestion.
    restarted = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not restarted.exception
    restarted.text_input[0].set_value("gravitational")
    next(button for button in restarted.button if button.label == "Find evidence").click().run()
    assert not restarted.exception
    assert any("energy_notes.pdf, page 2" in text.value for text in restarted.text)
    next(button for button in restarted.button if button.label == "Preview original page").click().run()
    assert not restarted.exception
    assert not restarted.error
    assert len(restarted.get("image")) == 1


def test_streamlit_empty_upload_and_no_results(tmp_path, monkeypatch):
    monkeypatch.setenv("TUTORTRACE_DATA_DIR", str(tmp_path))
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    next(button for button in app.button if button.label == "Ingest documents").click().run()
    assert any("Choose at least one" in warning.value for warning in app.warning)
    app.text_input[0].set_value("unknown")
    next(button for button in app.button if button.label == "Find evidence").click().run()
    assert not app.exception
    assert any("No matching evidence" in item.value for item in app.info)


def test_streamlit_real_upload_batch_failure_and_duplicate(tmp_path, monkeypatch, pdf_bytes, pptx_bytes):
    monkeypatch.setenv("TUTORTRACE_DATA_DIR", str(tmp_path))
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    app.file_uploader[0].set_value([
        ("lesson.pdf", pdf_bytes, "application/pdf"),
        ("broken.pdf", b"corrupt", "application/pdf"),
        ("lesson.pptx", pptx_bytes, "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
    ])
    next(button for button in app.button if button.label == "Ingest documents").click().run()
    assert not app.exception
    assert len(app.success) == 2
    assert len(app.error) == 1
    assert "broken.pdf" in app.error[0].value
    store = Store(tmp_path / "tutortrace.sqlite3")
    assert len(store.list_documents()) == 2
    assert [row["status"] for row in store.recent_attempts()] == ["indexed", "failed", "indexed"]
    app.file_uploader[0].set_value(("renamed.pdf", pdf_bytes, "application/pdf"))
    next(button for button in app.button if button.label == "Ingest documents").click().run()
    assert not app.exception
    assert any("Already preserved" in item.value for item in app.info)
    assert len(store.list_documents()) == 2
    app.text_input[0].set_value("chlorophyll")
    next(button for button in app.button if button.label == "Find evidence").click().run()
    assert not app.exception
    assert any("lesson.pptx, slide 3" in text.value for text in app.text)
