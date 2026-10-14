"""Assessment and revision UI; all grading remains in the tested service layer."""

import streamlit as st

from tutortrace.assessment import verify_question
from tutortrace.errors import TutorTraceError
from tutortrace.ingestion.pdf import render_pdf_page
from tutortrace.learning import LearningStore, recommendations, revision_request


def _source(store, evidence, key):
    st.text(evidence.citation)
    st.text(evidence.text)
    st.caption(f"Source ID: {evidence.document_id} · Chunk: {evidence.chunk_id}")
    if evidence.source_type == "pdf" and st.button("View cited PDF page", key=f"learning_preview_{key}"):
        st.image(render_pdf_page(store.original(evidence.document_id), evidence.location), caption=evidence.citation)
    if evidence.source_type == "pptx":
        st.caption(f"Open the downloaded presentation at slide {evidence.location}.")
    st.download_button("Download assessment source", store.original(evidence.document_id),
                       file_name=evidence.filename, key=f"learning_download_{key}")


def _quiz(store, learning, learner_id, session):
    if not session:
        return
    st.write(f"{'Diagnostic' if session['diagnostic'] else 'Practice'} · {session['topic']['label']} · {session['difficulty']}")
    if session["status"] == "open":
        st.caption("The answer review appears after submission. Practice is open-book; an unfinished quiz survives a restart.")
        # Fail closed if a source was re-indexed or the question bank was altered.
        valid = True
        for question in session["questions"]:
            try:
                verify_question(store, question)
            except TutorTraceError as exc:
                st.warning(f"This quiz cannot be graded: {exc}")
                valid = False
                break
        if valid:
            with st.form(f"quiz_{session['id']}"):
                responses = {}
                for number, question in enumerate(session["questions"], 1):
                    st.text(f"{number}. {question.prompt}")
                    evidence = verify_question(store, question)
                    st.caption(evidence.citation + f" · {question.kind}")
                    key = f"answer_{session['id']}_{question.id}"
                    if question.kind == "mcq":
                        responses[question.id] = st.radio("Choose an answer", question.options, index=None, key=key)
                    else:
                        responses[question.id] = st.text_input("Your answer", key=key, max_chars=500)
                submitted = st.form_submit_button("Grade assessment", type="primary")
            if submitted:
                learning.submit(store, learner_id, session["id"], responses)
                st.rerun()
        if st.button("Abandon unfinished assessment", key=f"abandon_{session['id']}"):
            learning.abandon(learner_id, session["id"])
            st.rerun()
    elif session["status"] == "completed":
        st.write("Answer review")
        attempts = {row["question_id"]: row for row in session["attempts"]}
        counts = {status: sum(row["status"] == status for row in attempts.values())
                  for status in ("correct", "incorrect", "needs_review")}
        st.write(f"{counts['correct']} matched · {counts['incorrect']} did not match · {counts['needs_review']} need review")
        for number, question in enumerate(session["questions"], 1):
            attempt = attempts[question.id]
            with st.expander(f"{number}. {attempt['status'].replace('_', ' ')} · {question.kind}"):
                st.text(question.prompt)
                st.text(f"Your answer: {attempt['response']}")
                try:
                    evidence = verify_question(store, question)
                    st.text(f"Verified source key: {question.answer}")
                    st.text(f"Supporting statement: {question.quote}")
                    _source(store, evidence, f"{session['id']}_{question.id}")
                except TutorTraceError as exc:
                    st.warning(f"Historical grade retained; current source verification unavailable: {exc}")
                st.write(attempt["feedback"])
                st.caption(f"Recorded recall estimate: {attempt['mastery_before']:.0%} → {attempt['mastery_after']:.0%}")
    else:
        st.caption("Last assessment was abandoned. It made no mastery changes.")


def learning_panel(store, documents):
    st.subheader("Adaptive practice")
    st.caption("Verified source-recall quizzes · Persistent local learner profiles · Personalized revision")
    st.info("Questions use deterministic source blanks, including numerical value recall. They do not test all forms of understanding. No AI inference is needed for quiz generation or grading.")
    try:
        learning = LearningStore(store.path.with_suffix(".learning.sqlite3"))
        with st.expander("Create a learner profile"):
            with st.form("new_learner"):
                name = st.text_input("Learner display name", max_chars=80, key="learning_name")
                create = st.form_submit_button("Create learner")
            if create:
                st.session_state["learning_learner"] = learning.create_learner(name)
        learners = learning.learners()
        if not learners:
            st.caption("Create a local profile to begin a diagnostic quiz. Profiles are not password-protected accounts.")
            return
        identifiers = [learner["id"] for learner in learners]
        if st.session_state.get("learning_learner") not in identifiers:
            st.session_state["learning_learner"] = identifiers[0]
        learner_id = st.selectbox("Active learner", identifiers, key="learning_learner",
                                  format_func=lambda value: next(f"{row['name']} · {value[:6]}" for row in learners if row["id"] == value))
        st.caption("Profile selection separates progress; this local demo does not provide authentication or access control.")
        session = learning.session(learner_id)
        with st.expander("Assessment generator", expanded=not session or session["status"] != "open"):
            with st.form("assessment_generator"):
                scopes = st.multiselect("Assessment documents / course", [doc.id for doc in documents],
                                        format_func=lambda value: next(f"{doc.filename} · {value[:8]}" for doc in documents if doc.id == value),
                                        key="learning_scope", help="Empty means all currently uploaded documents. Progress is tracked separately for each document selection.")
                topic = st.text_input("Practice topic", value="energy", max_chars=120, key="learning_topic",
                                      help="Use keywords appearing together in source statements, such as kinetic energy.")
                difficulty = st.selectbox("Practice difficulty", ["adaptive", "easy", "medium", "hard"], key="learning_difficulty")
                kinds = st.multiselect("Question formats", ["mcq", "short", "numerical"], default=["mcq", "short", "numerical"], key="learning_kinds",
                                      format_func=lambda value: {"mcq": "Multiple choice", "short": "Short answer (exact source wording)", "numerical": "Numerical value recall"}[value])
                count = st.slider("Questions requested", 1, 8, 3, key="learning_count")
                generate = st.form_submit_button("Generate assessment", disabled=bool(session and session["status"] == "open"))
            if generate:
                learning.begin(store, learner_id, topic, document_ids=tuple(scopes), difficulty=difficulty, kinds=tuple(kinds), count=count)
                st.rerun()
            st.caption("First objectively graded practice in a topic is diagnostic. Adaptive difficulty starts easy. Recent facts from your last two quizzes are withheld; fewer questions may be available. Easy/medium/hard change recall scaffolding, not a calibrated difficulty measure.")
        _quiz(store, learning, learner_id, session)
        dashboard = learning.dashboard(learner_id)
        st.write("Topic mastery estimates")
        st.caption("Recall estimate = (1 + correct) / (2 + correct + incorrect). A new topic starts at 50%, meaning unknown—not measured mastery. Unverified wording does not update the estimate. These estimates are not calibrated knowledge probabilities.")
        if not dashboard:
            st.caption("No learning history yet. Generate your first diagnostic assessment.")
        else:
            st.dataframe([{"Topic": row["label"], "Course ID": row["topic_id"][:8], "Recall estimate": f"{row['score']:.0%}",
                           "Correct": row["correct"], "Incorrect": row["incorrect"], "Needs review": row["review"],
                           "Next difficulty": row["next_difficulty"]} for row in dashboard], hide_index=True, width="stretch")
            st.write("Revision priorities")
            for rec in recommendations(store, learning, learner_id):
                topic_row = rec["topic"]
                with st.container(border=True):
                    st.write(topic_row["label"])
                    st.write(rec["reason"])
                    if not rec["evidence"]:
                        st.warning("No currently verified revision evidence found for this topic.")
                        continue
                    with st.expander("Source-backed revision and prerequisites"):
                        for index, evidence in enumerate(rec["evidence"]):
                            _source(store, evidence, f"revision_{learner_id}_{topic_row['topic_id']}_{index}")
                        if rec["foundations"]:
                            st.write("The material explicitly names these foundations:")
                            for foundation in rec["foundations"]:
                                st.text(foundation["statement"])
                                st.caption(foundation["evidence"].citation)
                        else:
                            st.caption("No explicit prerequisite statement found. No prerequisite relationship has been inferred.")
                    if st.button("Revise with AI tutor", key=f"revise_{learner_id}_{topic_row['topic_id']}"):
                        question, scopes = revision_request(rec)
                        st.session_state["tutor_question"] = question
                        st.session_state["tutor_scope"] = list(scopes)
                        st.session_state.pop("tutor_result", None)
                        st.info("Revision question and document selection prepared in AI Tutor below. Press Ask AI tutor to run inference.")
        history = learning.history(learner_id)
        with st.expander("Learning history and progress"):
            if history:
                st.dataframe([{"Topic": row["label"], "Difficulty": row["difficulty"], "Diagnostic": bool(row["diagnostic"]),
                               "Result": row["status"], "Review signal": row["misconception"], "Time (UTC)": row["created_at"],
                               "Estimate after": row["mastery_after"]} for row in history], hide_index=True, width="stretch")
                st.caption("Review signals record answer mismatches; they are not diagnoses of a student's underlying misconception.")
                st.line_chart([{"Attempt": index, "Recall estimate": row["mastery_after"],
                                "Topic": f"{row['label']} · {row['topic_id'][:6]}"} for index, row in enumerate(history, 1)],
                               x="Attempt", y="Recall estimate", color="Topic")
                older = [item for item in learning.sessions(learner_id) if item["id"] != session["id"]]
                if older:
                    selected = st.selectbox("Review earlier assessment", [item["id"] for item in older],
                                            key=f"learning_history_{learner_id}",
                                            format_func=lambda value: next(f"{item['label']} · {item['created_at']} · {item['status']}" for item in older if item["id"] == value))
                    _quiz(store, learning, learner_id, learning.session(learner_id, selected))
            else:
                st.caption("No submitted answers yet.")
    except TutorTraceError as exc:
        st.warning(str(exc))
