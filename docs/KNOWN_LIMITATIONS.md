# Known limitations — Milestone 2

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
- Chat answers are session-local and are not a persistent conversation or learner
  model. No quizzes, mastery tracking, adaptive personalization, learning-outcome
  measurements or independent external benchmark is implemented.
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
- Tests cover the local library and Streamlit application harness. Native browser
  file selection/download interaction and visual layout require a manual review.
- PyMuPDF has AGPL/commercial license terms. No repository-wide distribution license
  has been chosen here; dependency licensing must be reviewed before distribution.

See `MILESTONE_2_VERIFICATION.md` for current checks and measurements, and the
Milestone 1 verification documents for historical baselines.
