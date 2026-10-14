"""Run with: python -m streamlit run app.py"""

from pathlib import Path
import os

import streamlit as st

from tutortrace.errors import TutorTraceError
from tutortrace.ingestion.pdf import render_pdf_page
from tutortrace.ingestion.service import ingest
from tutortrace.persistence import Store
from tutortrace.retrieval.search import search
from tutortrace.tutor_ui import tutor_panel

ROOT = Path(__file__).resolve().parent


def ingest_files(store, files):
    for name, data in files:
        with st.spinner(f"Reading {name}…"):
            try:
                result = ingest(store, name, data)
                document = result.document
                if result.duplicate:
                    st.info(f"Already preserved: {document.filename}. No duplicate passages were added.")
                elif result.reindexed:
                    st.success(f"Reindexed {document.filename} with the current extraction pipeline: {document.chunk_count} passages.")
                    if document.status == "empty":
                        st.warning("Original preserved, but no extractable text was found.")
                elif document.status == "empty":
                    st.warning(f"{document.filename}: original preserved, but no extractable text was found.")
                else:
                    st.success(f"Indexed {document.filename}: {document.unit_count} source units, {document.chunk_count} passages.")
            except TutorTraceError as exc:
                st.error(f"{name}: {exc}")


def main():
    st.set_page_config(page_title="TutorTrace AI · Evidence library", page_icon="📚", layout="wide")
    st.title("TutorTrace AI")
    st.write("Find evidence in your learning materials, with its original page or slide.")
    st.caption("Document library · Evidence search · Source-grounded AI tutor")
    data_dir = Path(os.environ.get("TUTORTRACE_DATA_DIR", str(ROOT / "data")))
    if not data_dir.is_absolute():
        data_dir = ROOT / data_dir
    try:
        store = Store(data_dir / "tutortrace.sqlite3")
    except TutorTraceError as exc:
        st.error(str(exc))
        st.stop()

    with st.sidebar:
        st.header("Add learning materials")
        with st.form("upload_form", clear_on_submit=True):
            uploads = st.file_uploader("PDF chapters or PowerPoint slides", type=["pdf", "pptx"], accept_multiple_files=True)
            submitted = st.form_submit_button("Ingest documents", type="primary")
        if submitted:
            if uploads:
                ingest_files(store, [(upload.name, upload.getvalue()) for upload in uploads])
            else:
                st.warning("Choose at least one document first.")
        st.caption("Up to 50 MiB per file. Originals stay in the local database. Identical files are indexed once.")
        if st.button("Load sample course"):
            paths = [ROOT / "demo_assets" / "energy_notes.pdf", ROOT / "demo_assets" / "energy_slides.pptx"]
            if all(path.is_file() for path in paths):
                ingest_files(store, [(path.name, path.read_bytes()) for path in paths])
            else:
                st.error("Sample files are missing. Restore demo_assets from the repository.")
        st.info("Text extraction only. Scans, pictures, diagrams and speaker notes are not interpreted.")

    try:
        documents = store.list_documents()
        st.subheader("Document library")
        if documents:
            st.dataframe([
                {"Document": doc.filename, "Format": doc.source_type.upper(), "Status": doc.status,
                 "Pages / slides": doc.unit_count, "Passages": doc.chunk_count, "Source ID": doc.id}
                for doc in documents
            ], hide_index=True, width="stretch")
            selected_id = st.selectbox("Original document", [doc.id for doc in documents],
                                       format_func=lambda value: next(f"{doc.filename} · {doc.id[:10]}" for doc in documents if doc.id == value))
            selected = next(doc for doc in documents if doc.id == selected_id)
            with st.expander("Source details and original download"):
                st.text(f"SHA-256: {selected.id}\nIngested (UTC): {selected.created_at}\nPipeline: {selected.pipeline_version}")
                for warning in selected.warnings:
                    st.warning(warning)
                st.download_button("Download original document", store.original(selected.id), file_name=selected.filename,
                                   mime="application/pdf" if selected.source_type == "pdf" else "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                                   key=f"original-{selected.id}")
        else:
            st.info("Upload a chapter or slide deck, or load the sample course to begin.")

        st.subheader("Search the evidence")
        with st.form("search_form"):
            query = st.text_input("Search your materials", placeholder="How is kinetic energy calculated?", max_chars=1000)
            scope = st.selectbox("Search scope", [None] + [doc.id for doc in documents],
                                 format_func=lambda value: "All documents" if value is None else next(f"{doc.filename} · {doc.id[:10]}" for doc in documents if doc.id == value))
            count = st.slider("Passages to show", min_value=1, max_value=20, value=5)
            run_search = st.form_submit_button("Find evidence", type="primary")
        if run_search:
            st.session_state["last_search"] = (query, count, scope)
        if "last_search" in st.session_state:
            active_query, count, scope = st.session_state["last_search"]
            results = search(store, active_query, count, scope)
            st.caption(f"Results for: {active_query}")
            if not results:
                st.info("No matching evidence found. Try keywords present in your materials. This does not establish whether an answer exists.")
            else:
                st.caption("Keyword matches ranked by SQLite BM25. These are source passages, not verified answers or confidence scores.")
                for position, evidence in enumerate(results, 1):
                    with st.container(border=True):
                        st.text(f"{position}. {evidence.citation}")
                        st.text(evidence.text)
                        with st.expander("Inspect citation and full source text"):
                            resolved = store.resolve_evidence(evidence.chunk_id)
                            st.text(f"Document ID: {resolved.document_id}\nUnit ID: {resolved.unit_id}\nChunk ID: {resolved.chunk_id}\nPipeline: {resolved.pipeline_version}\nText offsets: [{resolved.start}, {resolved.end})")
                            st.text(resolved.unit_text)
                            st.caption("Offsets refer to normalized extracted text. Whitespace and reading order may differ from the original layout.")
                        if evidence.source_type == "pdf" and st.button("Preview original page", key=f"preview-{evidence.chunk_id}"):
                            try:
                                preview = render_pdf_page(store.original(evidence.document_id), evidence.location)
                                st.image(preview, caption=evidence.citation)
                            except TutorTraceError:
                                raise
                            except Exception:
                                st.error("The original page could not be rendered. Download the source to inspect it.")
                        elif evidence.source_type == "pptx":
                            st.caption(f"Open the original PowerPoint from the library and go to slide {evidence.location}.")
        with st.expander("Recent ingestion history"):
            attempts = store.recent_attempts()
            if attempts:
                st.dataframe([{key: row[key] for key in ("filename", "status", "message", "created_at")} for row in attempts],
                             hide_index=True, width="stretch")
            else:
                st.caption("No ingestion attempts recorded yet.")
        tutor_panel(store, documents)
    except TutorTraceError as exc:
        st.error(str(exc))


if __name__ == "__main__":
    main()
