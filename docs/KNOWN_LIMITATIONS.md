# Known limitations — Milestone 3

- PDF/PPTX text only. No video/audio, OCR, vision models, image/diagram interpretation,
  embedded chart semantics, PPTX speaker notes or animation semantics. Scanned PDFs
  can be stored as `empty`; mixed text/image documents index only extracted text.
- PDF layout reading order and PPTX shape order can differ from visual reading
  order. Tables are linearized. Equations, columns and unusual fonts can extract
  imperfectly. PDF citations always use physical page positions. Optional labels
  come only from PDF page-label metadata, which may itself differ from the printed
  document. Printed numbers are never inferred from page text.
- Dehyphenation joins letter continuations only within a PDF text block; it can
  remove a genuine compound-word hyphen at a line break. Separate blocks/pages
  are never joined. This is a bounded extraction heuristic, not language-aware
  spelling correction. Ligature expansion depends on the font's text mapping.
- The original search interface uses keywords, English stopwords and OR matching.
  The AI Tutor additionally offers optional local embedding retrieval and rank fusion;
  neither path has a learned reranker, topic model or calibrated confidence score.
  Broad queries can return weakly relevant passages. No-result search is not proof
  that the material lacks an answer. BM25 is not confidence.
- Query normalization now uses the same SQLite `unicode61` tokenizer as the index.
  Selected German, accented Latin, Turkish, Greek and Cyrillic examples are tested;
  complete multilingual support is not claimed. There is no language-specific
  segmentation, locale-aware casing or transliteration (`Straße` does not match
  `strasse`). English stopwords still apply to all queries.
- Chunk overlap can return similar passages from the same page. Original search does not
  deduplicate nearby hits. Long unbroken strings can be split inside a word.
  Tutor context suppresses redundant windows but can still include adjacent passages.
- Byte-identical duplicate detection only. Regenerating/resaving a PDF or PPTX can
  change its hash even if the content looks identical.
- Original PDFs can be previewed at the exact page. PPTX citations expose the
  original slide number and extracted text; no rendered slide preview or automatic
  navigation inside PowerPoint is implemented.
- The AI Tutor generates source-constrained explanations; citation/quote validation
  does not prove every claim is semantically supported. A model can misinterpret a
  valid quote, miss a contradiction, or mishandle an adversarial document. Unsupported
  aspects and abstention rely partly on model judgment. No independent entailment
  model or formal guarantee of faithfulness is implemented.
- Local CPU inference can take tens of seconds and may fail under memory pressure.
  Availability checks confirm installation, not successful generation. A socket
  timeout does not guarantee immediate cancellation of server-side computation.
  The app never downloads models or stops unrelated processes automatically.
- Semantic retrieval defaults to 500 corpus passages, a heuristic cosine threshold
  and a persistent embedding cache. Larger selections explicitly fall back to
  keyword retrieval; they are not silently sampled. Cache entries are not pruned
  automatically. Context character limits are not tokenizer-exact limits; reduce
  context for small models and unusually token-dense text.
- In the recorded diagnostic set, hybrid retrieval selected more irrelevant source
  units than keyword retrieval (label precision 14/26 versus 14/21). A separate
  no-keyword paraphrase probe recovered the relevant power slide at rank 2, behind
  an irrelevant passage. Semantic retrieval is therefore opt-in, not advertised
  as an across-the-board accuracy improvement.
- The real model sometimes lists unasked topics in `unsupported_aspects`. These
  are visibly labelled as not established, not accepted factual answer claims.
  Explicit abstentions discard all accompanying generated claims and citations;
  this conservative behavior can also discard a usable answer.
- The remote OpenAI-compatible adapter is contract-tested with synthetic responses;
  no live remote provider was tested with credentials. API variations may require
  adapter changes. Remote use sends selected excerpts and the question to that service.
- Chat answers remain session-local. Learner profiles, assessments, objective
  grades, review signals and topic estimates now persist separately. There is no
  persistent conversational memory or independent external learning benchmark.
- Assessments are deterministic source-cloze recall exercises. Numerical items
  recall a stated value; they do not verify source arithmetic or generate new
  calculation problems. Distractors can be easy to distinguish. Topic matching
  and sentence segmentation are bounded lexical heuristics, principally for
  English prose, rather than broad semantic question generation.
- Short-answer paraphrases receive `needs_review` and no mastery change. There is
  no subjective grader or teacher adjudication interface. A verified key means the
  key matches the source transformation, not that the source is true or that the
  student understands the concept. Practice is open-book.
- Mastery is an uncalibrated Beta(1,1) estimate of source-recall success. It does not
  model guessing, forgetting, item discrimination or different difficulty weights.
  Difficulty changes scaffolding; no psychometric validation is claimed. Review
  signals record mismatches, not established cognitive misconceptions.
- Recommendations cover tracked topic/course combinations only. Explicit
  prerequisite wording is recognized in a small set of source patterns; there is
  no inferred curriculum graph. Topic/course names and labels are student-selected.
  A changed document selection creates separate progress even for the same label.
- Question generation uses at most 12 passages / 12,000 characters. The last two
  issued quizzes' facts are withheld, including abandoned quizzes. Small corpora
  can exhaust the pool; withheld facts are not reused to fill the gap. Content
  duplicated across different documents can still be conceptually repetitive.
- Learner state and source data are separate SQLite files. Back up both. Source
  re-indexing or generator changes can retire cached questions; old grades remain
  but stale citations are flagged. There is no historical source-chunk archive or
  distributed transaction spanning both databases.
- The personalization evaluation uses prescribed simulated responses. Completion,
  repetition, recommendation and estimate changes test software behavior; they
  demonstrate no real-student learning gains or calibrated model quality.
- No accounts, auth, encryption at rest, deletion UI, backups UI, or multi-tenant
  security. Use only as a loopback/local app. The database includes original uploads.
- Parsing is synchronous. PDFs use separate processes with a 60-second timeout;
  PPTX parsing remains in-process. Size/expansion/unit limits do not provide
  hard memory guarantees or a full sandbox against hostile documents. Maximum-size documents
  and heavy multi-user traffic have not been performance-tested.
- Password-protected PDFs and legacy `.ppt` are rejected. Valid blank documents
  persist without searchable chunks. Corrupt uploads retain failure metadata only.
- A process interrupted before commit leaves no searchable partial document; its
  incomplete attempt is not recorded. If SQLite cannot write, failure logging cannot
  be guaranteed. Disk-full behavior is not directly simulated; rollback is tested
  with injected SQLite trigger failures and an actual child-process exit during
  re-indexing.
- Schema 1 upgrades transactionally to schema 2; there is no downgrade path or
  backup UI. Older application builds cannot open schema 2. Keep a database backup
  before changing application versions if rollback to the old build is needed.
  Unknown nonempty unversioned databases and future schema versions are rejected.
- Schema migration does not re-extract documents. Older evidence remains readable
  with its stored pipeline version; re-upload identical source bytes to apply the
  current pipeline. There is no bulk re-index UI. Successful re-indexing retires
  previous chunk IDs; document IDs and physical locations remain stable. Ordinary
  same-version duplicates do not repair damaged evidence.
- Tests cover the local library, learner transactions and Streamlit application
  harness. A live-browser sample-course quiz was also exercised. Native file
  selection and download behavior across different browsers still need broader review.
- PyMuPDF has AGPL/commercial license terms. No repository-wide distribution license
  has been chosen here; dependency licensing must be reviewed before distribution.

See `MILESTONE_3_VERIFICATION.md` for current checks, `LEARNING_MODEL.md` for the
assessment/estimate contract, and the earlier milestone verification documents
for historical baselines.
