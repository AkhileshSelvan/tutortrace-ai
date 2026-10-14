# Reproducible tutoring diagnostics

`cases.json` is a small self-authored set: six generated documents, thirteen
questions, and physical page/slide labels. The calibration notes deliberately
contradict each other. The untrusted note deliberately contains an instruction
injection. All educational fixtures are generated locally from the supplied text;
no private source documents or credentials are needed.

Run `python -m scripts.evaluate_tutor` for retrieval only, add `--real` for actual
configured-provider inference, or `--hybrid` for local embedding retrieval. These
options can be combined. `--only` takes question IDs for targeted diagnosis.
Use `--output data/run-name.json` to retain an individual run.

The report records every case, expected and retrieved source locations, exact
denominators, provider parameters, errors and elapsed time. Real runs additionally
record generated claims, raw model completions and canonical citation evidence.
Outputs contain only this synthetic corpus; do not use this recording runner with
private educational material without considering where the resulting report goes.

Metrics are intentionally limited:

- All-expected-source retrieval: questions where every labelled source is selected,
  divided by questions with source labels. Unsupported questions are excluded.
- Source recall and selected-source precision: physical source-unit counts against
  the labels, not chunk-level semantic relevance judgments.
- Citation validity: accepted references and exact quotes belonging to the request's
  evidence, divided by displayed references. Invalid responses are rejected and
  separately counted as errors, not hidden inside a perfect citation fraction.
- Unsupported abstention: actual abstentions on unsupported questions; failures
  are not credited as abstention. Empty retrieval and model abstention are separated.
- Expected status and expected-term checks: simple diagnostic assertions, not a
  faithfulness or correctness score. Ambiguous questions intentionally allow several
  defensible statuses; inspect the generated content too.
- Latency: wall-clock retrieval plus inference and any model loading, on the
  current machine and workload. It is not a general performance benchmark.

The set is used for development, is small, and has no held-out split. Do not infer
general model quality, prompt-injection immunity, or learning gains from it.
