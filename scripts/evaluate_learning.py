"""Reproducible scripted learners, with source inputs and every observed outcome.

Run: python -m scripts.evaluate_learning --output docs/evaluation/m3-simulation.json
All temporary databases stay below data/. No model or remote service is used.
"""

import argparse
from decimal import Decimal
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

from scripts.create_demo_assets import make_pdf, make_pptx
from tutortrace.assessment import verify_question
from tutortrace.ingestion.service import ingest
from tutortrace.learning import LearningStore, recommendations
from tutortrace.persistence import Store

ROOT = Path(__file__).resolve().parents[1]


def stable_pptx(slides):
    output = BytesIO()
    with ZipFile(BytesIO(make_pptx(slides))) as source, ZipFile(output, "w") as target:
        for name in sorted(source.namelist()):
            info = ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            target.writestr(info, source.read(name))
    return output.getvalue()


def material_inputs(count):
    return [
        {"topic": "kinetic energy", "filename": "kinetic.pdf", "units": [
            f"Kinetic energy of a 2 kg cart moving at {index} m/s is {index * index} joules."
            for index in range(1, count + 1)]},
        {"topic": "power", "filename": "power.pptx", "units": [
            f"Power for a lamp transferring {index * 10} joules in 2 seconds is {index * 5} watts."
            for index in range(1, count + 1)]},
        {"topic": "potential energy", "filename": "potential.pptx", "units": [
            f"Using gravity 10 m/s squared, potential energy of a 1 kg book at height {index} m is {index * 10} joules."
            for index in range(1, count + 1)]},
    ]


def run(config, directory):
    started = time.perf_counter()
    expected_sessions = config["rounds"] * len(config["topic_order"])
    for profile in config["profiles"]:
        if (len(profile["responses"]) != expected_sessions
                or any(len(bits) != config["questions_per_session"] or set(bits) - {"0", "1"}
                       for bits in profile["responses"])):
            raise ValueError("Simulation response inputs do not match the configured sessions/questions.")
    source = Store(directory / "source.sqlite3")
    learning = LearningStore(directory / "source.learning.sqlite3")
    inputs = material_inputs(config["source_examples_per_topic"])
    docs = {}
    for item in inputs:
        content = make_pdf(tuple(item["units"])) if item["filename"].endswith(".pdf") else stable_pptx(tuple(item["units"]))
        document = ingest(source, item["filename"], content).document
        docs[item["topic"]] = document.id
        item["document_id"] = document.id
    report = {"configuration": config, "source_inputs": inputs,
              "interpretation": "Deterministic software simulation. Response correctness is prescribed, not learned. Estimate changes do not demonstrate improved learning.",
              "provider": "none; deterministic source-recall generation and grading", "profiles": []}
    for profile in config["profiles"]:
        learner = learning.create_learner(profile["name"])
        sessions = []
        seen = set()
        recent = []
        repeated_ever = repeated_recent = completed_questions = changes = 0
        previous_top = None
        for index, bits in enumerate(profile["responses"]):
            topic = config["topic_order"][index % len(config["topic_order"])]
            sid = learning.begin(source, learner, topic, document_ids=(docs[topic],),
                                 kinds=tuple(config["formats"]), count=config["questions_per_session"])
            session = learning.session(learner, sid)
            records = []
            responses = {}
            facts = {q.fact_id for q in session["questions"]}
            recent_facts = set().union(*recent[-2:]) if recent else set()
            repeated_ever += len(facts & seen)
            repeated_recent += len(facts & recent_facts)
            for question, bit in zip(session["questions"], bits, strict=True):
                evidence = verify_question(source, question)
                response = question.answer
                if bit == "0":
                    response = (str(Decimal(question.answer) + 1) if question.kind == "numerical" else
                                next(option for option in question.options if option != question.answer))
                responses[question.id] = response
                records.append({"question_id": question.id, "fact_id": question.fact_id, "format": question.kind,
                                "source_document": evidence.document_id, "source_location": evidence.location,
                                "citation": evidence.citation, "excerpt": question.quote,
                                "prompt": question.prompt, "verified_key": question.answer, "response": response})
            learning.submit(source, learner, sid, responses)
            completed_questions += len(records)
            current = learning.dashboard(learner)
            recs = recommendations(source, learning, learner)
            top = recs[0]["topic"]["label"]
            changes += previous_top is not None and top != previous_top
            previous_top = top
            sessions.append({"number": index + 1, "topic": topic, "difficulty": session["difficulty"],
                             "diagnostic": bool(session["diagnostic"]), "response_pattern": bits,
                             "questions": records, "status": learning.session(learner, sid)["status"],
                             "mastery_after": {row["label"]: row["score"] for row in current},
                             "revision_priority": top})
            seen.update(facts)
            recent.append(facts)
        before_restart = learning.dashboard(learner)
        # New objects/connections, exactly the application's persistent storage boundary.
        learning = LearningStore(learning.path)
        source = Store(source.path)
        persisted = learning.dashboard(learner) == before_restart
        profile_report = {"name": profile["name"], "sessions_completed": len(sessions),
                          "sessions_requested": len(profile["responses"]),
                          "questions_completed": completed_questions,
                          "questions_requested": len(profile["responses"]) * config["questions_per_session"],
                          "repeated_facts_ever": repeated_ever, "repeated_facts_within_two_sessions": repeated_recent,
                          "repeat_denominator": completed_questions, "recommendation_changes": changes,
                          "recommendation_transition_denominator": max(0, len(sessions) - 1),
                          "difficulty_sequence": [item["difficulty"] for item in sessions],
                          "final_mastery": {row["label"]: {"estimate": row["score"], "correct": row["correct"],
                                                          "incorrect": row["incorrect"], "review": row["review"]} for row in before_restart},
                          "restart_preserved": persisted, "sessions": sessions}
        report["profiles"].append(profile_report)
    report["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "evaluation/learning_profiles.json")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/evaluation/m3-simulation.json")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    (ROOT / "data").mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="learning-eval-", dir=ROOT / "data") as temporary:
        report = run(config, Path(temporary))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"profiles": [{key: value for key, value in item.items() if key != "sessions"} for item in report["profiles"]],
                      "elapsed_seconds": report["elapsed_seconds"], "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
