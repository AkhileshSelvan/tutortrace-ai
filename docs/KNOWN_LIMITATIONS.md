# Known limitations — Milestone 1

- PDF/PPTX text only. No video/audio, OCR, vision models, image/diagram interpretation,
  embedded chart semantics, PPTX speaker notes or animation semantics. Scanned PDFs
  can be stored as `empty`; mixed text/image documents index only extracted text.
- PDF layout reading order and PPTX shape order can differ from visual reading
  order. Tables are linearized. Equations, columns and unusual fonts can extract
  imperfectly. PDF citations use physical page positions, not printed page labels.
- Keyword search with English stopwords, OR matching and SQLite Unicode tokenization;
  no embeddings, synonyms, stemming, reranker, topic model or semantic threshold.
  Broad queries can return weakly relevant passages. No-result search is not proof
  that the material lacks an answer. BM25 is not confidence.
- Chunk overlap can return similar passages from the same page. Search does not
  deduplicate nearby hits. Long unbroken strings can be split inside a word.
- Byte-identical duplicate detection only. Regenerating/resaving a PDF or PPTX can
  change its hash even if the content looks identical.
- Original PDFs can be previewed at the exact page. PPTX citations expose the
  original slide number and extracted text; no rendered slide preview or automatic
  navigation inside PowerPoint is implemented.
- No LLM implementation or generated responses. The provider protocol is an
  extension point, not a tested model integration. No quizzes, learner mastery,
  adaptive tutoring, learning outcome measurements or external benchmarks yet.
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
  with an injected SQLite trigger failure.
- Schema version 1 has no upgrade/downgrade migrations or extraction reindex UI.
  Existing duplicates retain their original pipeline version. A future extraction
  change must explicitly handle older IDs and stored evidence.
- Tests cover the local library and Streamlit application harness. Native browser
  file selection/download interaction and visual layout require a manual review.
- PyMuPDF has AGPL/commercial license terms. No repository-wide distribution license
  has been chosen here; dependency licensing must be reviewed before distribution.

See `MILESTONE_1_VERIFICATION.md` for executed checks and unresolved defects, if any.
