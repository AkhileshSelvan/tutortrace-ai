"""Streamlit tutor panel; the existing library/search remains independent."""

import os

import streamlit as st

from tutortrace.errors import TutorTraceError
from tutortrace.ingestion.pdf import render_pdf_page
from tutortrace.providers.adapters import OllamaEmbedder, make_provider
from tutortrace.providers.llm import ProviderConfig
from tutortrace.retrieval.context import ContextConfig
from tutortrace.tutoring import ask


def tutor_panel(store, documents):
    st.subheader("AI Tutor")
    st.caption("Ask about your materials. Answers use selected evidence; library search works even when AI is unavailable.")
    try:
        config = ProviderConfig.from_env()
        provider = make_provider(config)
    except TutorTraceError as exc:
        st.error(str(exc))
        return
    st.write(f"Provider: {config.provider} · Model: {config.model}")
    if config.provider != "ollama":
        st.info("Remote inference sends your question and selected excerpts to the configured provider when you ask.")
    if st.button("Check model status", key="tutor_status"):
        status = provider.status()
        (st.success if status.available else st.warning)(status.message)
    with st.form("tutor_form"):
        scope = st.multiselect("Tutor documents / course", [doc.id for doc in documents],
                               key="tutor_scope",
                               format_func=lambda value: next(f"{doc.filename} · {doc.id[:10]}" for doc in documents if doc.id == value),
                               help="Choose several documents as a course. Empty selection searches all documents.")
        question = st.text_area("Student question", max_chars=1000, placeholder="How do kinetic energy and power differ?", key="tutor_question")
        semantic = st.checkbox("Include semantic retrieval (local embedding model)", value=False,
                               help="Find paraphrases; the first request may take longer. Failures are shown explicitly.")
        with st.expander("Evidence limits"):
            passages = st.slider("Maximum tutor passages", 1, 12, 5)
            characters = st.slider("Maximum source characters", 1200, 12000, 3600, step=300)
        submitted = st.form_submit_button("Ask AI tutor", type="primary")
    if submitted:
        with st.spinner("Finding evidence and asking the model…"):
            embedder = OllamaEmbedder(model=os.getenv("TUTORTRACE_EMBED_MODEL", "nomic-embed-text:latest"),
                                      base_url=os.getenv("TUTORTRACE_EMBED_URL", "http://127.0.0.1:11434")) if semantic else None
            result = ask(store, question, provider, document_ids=tuple(scope),
                         config=ContextConfig(max_passages=passages, max_characters=characters), embedder=embedder)
            st.session_state["tutor_result"] = (str(store.path), result)
    saved = st.session_state.get("tutor_result")
    if not saved or saved[0] != str(store.path):
        return
    result = saved[1]
    st.text(f"Question: {result.question}")
    st.caption(f"{result.provider} / {result.model} · {result.context.mode} retrieval · {result.elapsed_seconds:.2f}s")
    for warning in result.context.warnings:
        st.warning(warning)
    if result.status == "error":
        st.error("AI answer unavailable: " + result.message)
        st.info("No AI answer has been accepted. Retrieved excerpts remain available below; retry after correcting the error.")
    elif result.status == "abstained":
        st.warning(result.message)
        st.caption("AI inference completed; answer abstained." if result.inference_succeeded else "Retrieval only; no AI inference performed.")
    else:
        (st.warning if result.status == "conflict" else st.success)(result.message)
        st.caption("AI inference completed. Citation and quote checks establish provenance, not semantic correctness of every claim.")
    cited = {}
    for index, claim in enumerate(result.claims, 1):
        st.text(f"{index}. {claim.text}")
        for support in claim.supports:
            item = support.evidence
            cited[item.chunk_id] = item
            with st.expander(f"Source for statement {index}: {item.citation}"):
                st.text(support.quote)
                st.text(f"Chunk ID: {item.chunk_id}")
    for aspect in result.unsupported_aspects:
        st.warning("Not established by the selected material: " + aspect)
    with st.expander("Inspect selected evidence and original sources"):
        for item in result.context.evidence:
            st.text(item.citation)
            st.text(item.text)
            st.caption("Cited in answer" if item.chunk_id in cited else "Retrieved context; not cited in answer")
            try:
                current = store.resolve_evidence(item.chunk_id)
                if current.text != item.text:
                    st.warning("This evidence changed. Ask again before relying on it.")
                    continue
                if item.source_type == "pdf" and st.button(f"Open PDF page {item.location}", key=f"tutor_preview_{item.chunk_id}"):
                    st.image(render_pdf_page(store.original(item.document_id), item.location), caption=item.citation)
                if item.source_type == "pptx":
                    st.caption(f"Download and open slide {item.location}; automatic PowerPoint navigation is unavailable.")
                st.download_button("Download cited original", store.original(item.document_id), file_name=item.filename,
                                   key=f"tutor_original_{item.chunk_id}")
            except TutorTraceError as exc:
                st.warning(str(exc))
