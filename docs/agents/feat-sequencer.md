# AGENT BRIEF — feat/sequencer  (M2 — core already green, harden it)

Read `../../IDEA_SCOPE.md` §6 and `../../CLAUDE.md` first.

## Mission
`src/sequencer/core.py` already passes its acceptance tests on the staged fixture.
Your job is to make it survive **real extracted data**, which will be messier than
the fixture. Do not rewrite it — harden it.

## Files you own
- `src/sequencer/`
- `tests/test_sequencer.py` and new test files
- `fixtures/case_*.json` (add new staged cases; **do not edit `case_demo.json`** —
  it is the demo fallback and other branches' tests depend on it)

**Forbidden:** `src/contracts.py` (FROZEN), `src/extraction/`, `src/register/`, `web/`, `src/app.py`.

## Known weaknesses to fix (in priority order)

### 1. Cycle safety ⚠️
If extraction emits A-needs-B and B-needs-A, `build_plan` currently produces two
mutually blocked items and **`next_single_action` becomes `None`** — the demo shows
nothing to do. Detect cycles, break them deterministically (e.g. earliest due date
wins), and surface the cycle as a visible note rather than silence.
**There must ALWAYS be a next single action, or an explicit honest statement of why not.**

### 2. Transitive blocking
Today O3-blocked-by-O2 only registers because O2 provides a key O3 needs. Verify a
3+ deep chain orders correctly, and that completing the root unblocks the chain one
step at a time (not all at once).

### 3. Duplicate detection robustness
`_similar` uses token overlap ≥0.6 on `asked_what` + exact-normalised `asked_by`.
Real data will have "Canara Bank" vs "Canara Bank Ltd, Khammam Branch". Loosen
`asked_by` to token-subset matching. **Guard against over-merging** — two genuinely
different obligations from the same office must NOT collapse. Add a test for both.

### 4. Mismatch classification (card 17)
`_classify_pair` handles initials/expansions. Add:
- case/whitespace-only differences → cosmetic
- Devanagari ↔ Latin transliteration of the same name → cosmetic (best-effort;
  if you can't do it reliably, return `unknown` with a reason — **never guess `cosmetic`**)
- genuinely different given names → blocking
- >2 distinct readings currently only compares the first two — handle N readings

### 5. Ordering
`_due_key` puts undated items last via `"9999-12-31"`. Confirm mixed date formats
from real extraction don't sort wrongly — normalise to ISO before comparing, and
if a date can't be parsed, treat it as undated rather than sorting on raw text.

## Rules
- **Pure logic. No network, no Sarvam calls, no I/O.** This module must stay
  testable without a key — it's the reason the fixture demo always works.
- Every existing test must keep passing. Add tests; don't weaken assertions.

## Acceptance test
> `py -3.12 -m pytest -q` green, including new tests for: a dependency cycle, a
> 3-deep chain, a near-duplicate that must merge, a same-office pair that must NOT
> merge, and an N-way name mismatch.

## Verify
```bash
py -3.12 -m pytest -q
py -3.12 -m scripts.run_case
```
Merge after `feat/extraction`.
