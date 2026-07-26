# AGENT BRIEF — feat/case-memory  (M4 — cheapest points on the board)

Read `../../IDEA_SCOPE.md` §3 (memory boundary), §6, §8 M4 and `../../CLAUDE.md`.

## Mission
Memory & Context is ×1 and most teams will leave it at L1. Getting to **L4** is
~30 minutes of work for 4 weighted points. The rubric needs *persisted, governed
continuity* — not chat history.

## Files you own
- `src/case_store/`
- `tests/test_memory.py` (new)
- `src/app.py::correct` and `::get_case` only

**Forbidden:** `src/contracts.py` (FROZEN), `src/sequencer/`, `src/extraction/`, `web/`.

⚠️ **Keep `load_case(case_id)` and `save_case(case)` signatures identical** — the app
and other branches depend on them. You may change everything behind them.

## What L4 requires (rubric wording)
> "combines the current task with useful prior history… a handoff receives a
> concise, accurate state rather than the entire raw transcript, and the next
> component continues without making the user restart."

## Tasks

### 1. Correction propagation (the demo beat)
`correct` exists but is thin. Make it provably propagate:
- patch every `FieldReading` matching `(doc_id, field_name)`
- rebuild the plan
- record `Correction.propagated_to` = **every obligation id whose plan state,
  mismatch, or blocking edge changed as a result** — computed by diffing the plan
  before and after, not guessed
- return the diff so the UI can show *"this correction cleared the O1↔O2 mismatch
  and unblocked O2"*

### 2. Resume after reload
`GET /api/case/{id}` must return the identical plan after a process restart.
Test it by writing, re-reading from disk in a fresh store instance, and comparing.

### 3. Case listing + reset (demo hygiene)
- `GET /api/cases` → `[{id, created, item_count, next_single_action}]`
- `POST /api/case/{id}/reset` → back to as-loaded state (M5 needs this for repeated runs)

### 4. Optional (only if 1–3 are done): stale vs current
When a correction supersedes an earlier reading, keep the old value visible as
superseded rather than deleting it. That is L5 language ("stale information is
distinguishable from current"). **Do not start this until 1–3 are merged.**

## Acceptance test
> Correct `owner_name` on the demo case once → the cosmetic mismatch clears, the
> `propagated_to` list names the affected obligations, the plan re-sequences, and
> **the same case reloaded from disk in a fresh process shows the corrected state.**

## Non-goals
No auth, no multi-tenant, no user accounts (IDEA_SCOPE.md §12). SQLite is optional —
the JSON store is sufficient for L4. Don't spend time on storage engineering.

## Verify
```bash
py -3.12 -m pytest -q
```
Merge after `feat/register`.
