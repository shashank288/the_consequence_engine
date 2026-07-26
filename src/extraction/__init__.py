"""feat/extraction — photographed page -> ObligationDraft.

    from src.extraction.pipeline import extract_drafts, presence_facts
    drafts = extract_drafts(["fixtures/private/register_page.png"])

Modules:
  pipeline.py    orchestration: Doc-Intelligence -> deterministic reader ->
                 (optional) sarvam-105b proposals -> verified ObligationDrafts
  confidence.py  how much we believe a field, earned from evidence on the page
  prompts.py     the normalisation prompt + the shared requirement-key vocabulary
  offline_sample.json
                 hand-authored stand-in replayed under SARVAM_OFFLINE=1.
                 NOT a real API capture — see the file's own _README.

The invariants this package exists to hold, in priority order:
  1. No requirement without a quote that is verbatim on the page.
  2. No invented deadline or amount. Absent is "absent"; unreadable is "refused".
  3. No confidence of 1.0 when the API supplied none.
  4. No forced document type — "unknown" is always available.

Status: verified end to end offline (tests/test_extraction.py). The live
Doc-Intelligence call is wired to the documented job flow and driven against
those shapes in tests, but has never run against the real API — there was no
SARVAM_API_KEY at build time. See docs/handoff/feat-extraction.md.
"""
