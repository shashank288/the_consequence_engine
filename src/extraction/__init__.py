"""feat/extraction — photographed page -> ObligationDraft.

    from src.extraction.pipeline import extract_drafts, presence_facts
    drafts = extract_drafts(["fixtures/private/register_page.png"])

Modules:
  pipeline.py    orchestration: Doc-Intelligence -> deterministic reader ->
                 (optional) sarvam-105b proposals -> verified ObligationDrafts
  confidence.py  how much we believe a field, earned from evidence on the page
  prompts.py     the normalisation prompt + the shared requirement-key vocabulary
  offline_sample.json
                 replayed under SARVAM_OFFLINE=1. MIXED PROVENANCE: the
                 register_page entry is a REAL captured response; the rest are
                 hand-authored stand-ins. See the file's own _README.

The invariants this package exists to hold, in priority order:
  1. No requirement without a quote that is verbatim on the page.
  2. No invented deadline or amount. Absent is "absent"; unreadable is "refused".
  3. No confidence of 1.0 when the API supplied none.
  4. No forced document type — "unknown" is always available.

Status: M0 VERIFIED — fixtures/private/register_page.png ran through the live
doc-digitization API on 2026-07-26 (9.4s), and POST /api/case runs it end to
end. The docs were wrong in five places and Sarvam's confidence turned out to be
per layout block rather than per field; both are written up in
docs/handoff/feat-extraction.md, which main needs for config.py + §5.
"""
