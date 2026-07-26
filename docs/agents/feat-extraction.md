# AGENT BRIEF — feat/extraction  ⚠️ CRITICAL PATH (M0 → M1)

Read `../../IDEA_SCOPE.md` §5, §8 (M0, M1) and `../../CLAUDE.md` before starting.

## Mission
Turn a **photographed document** into `list[ObligationDraft]`. You own the only
unverified external dependency in the project. Everything else is already green.

## Files you own (touch NOTHING else)
- `src/sarvam_client.py`
- `src/extraction/` (create `pipeline.py`, `prompts.py`)
- `fixtures/raw/` (cache every raw API response here — git-ignored)
- `tests/test_extraction.py` (new)

**Forbidden:** `src/contracts.py` (FROZEN), `src/sequencer/`, `web/`, `src/case_store/`.

## Task 1 — M0, do this FIRST (deadline 13:15)
Implement `doc_intelligence_extract(image_path)` in `src/sarvam_client.py` against the
async job flow already documented in that file's docstring. Then run ONE real
photographed page through it and **record the actual request/response shapes as
comments in the file**. Cache the raw JSON to `fixtures/raw/`.

```bash
py -3.12 -c "from src.sarvam_client import doc_intelligence_extract as f; import json; print(json.dumps(f('fixtures/private/<page>.jpg'), indent=2)[:3000])"
```

**If the job API fails or shapes don't match by 13:15:** STOP, report to main, and
switch to the fallback in IDEA_SCOPE.md §8 M0 (Akshar Studio manual export → JSON).
Do not burn an hour debugging. Say so immediately.

**If no API key yet:** build everything against a recorded fixture in
`fixtures/raw/sample_docintel.json` and add a `SARVAM_OFFLINE=1` env switch that
replays it. Wire the real call the moment the key lands.

## Task 2 — M1: pipeline
`src/extraction/pipeline.py`:

```python
def extract_drafts(image_paths: list[str]) -> list[ObligationDraft]
```

1. Doc-Intelligence per image → text + regions + confidences.
2. `sarvam_client.chat()` normalisation (prompt in `prompts.py`) → one `ObligationDraft`
   per document. The LLM MUST return JSON matching `ObligationDraft`.
3. Map every field to `FieldReading` with a real `confidence` and a `SourceRef`
   carrying `doc_id`, `page`, and the **exact `quote`** from the page.
4. Set `unknown=True` when the doc type can't be determined — never force a type.

### Non-negotiable rules
- **Every `Requirement` needs a verbatim `quote` from the page. No quote → do not
  emit the requirement.** This is the Creativity claim; a hallucinated dependency
  destroys it.
- Never invent a `due` or `amount`. Absent → `status="absent"`. Unreadable →
  `status="refused"`, `value=None`. The sequencer applies the 0.75 threshold, but
  if the API gives you no confidence, set it honestly low, not 1.0.
- Prompt must forbid asserting law/procedure not on the page (IDEA_SCOPE.md §12).

## Acceptance test (must pass before PR)
> One **real photographed** document runs end to end and produces an
> `ObligationDraft` whose deadline field is either read-with-confidence or
> `refused` — never silently wrong — and whose requirements each carry a verbatim quote.

Add it as `tests/test_extraction.py` using a cached fixture so it runs without a key.

## Then wire the app
Replace the `501` in `src/app.py::create_from_uploads` — **this is the ONE file
outside your folder you may touch, and only that function.** Save uploads to a temp
dir, call `extract_drafts`, build a `Case`, `build_plan`, `save_case`, return it.

## Verify + PR
```bash
py -3.12 -m pytest -q      # ALL tests, not just yours
py -3.12 -m scripts.run_case   # fixture path must still work
git add -A && git commit -m "feat(extraction): ..." && git push -u origin feat/extraction
```
Merge order: **you go first.** Report shapes to main as soon as M0 lands.
