# AGENT BRIEF — feat/ui  (M2–M4 — fully unblocked, start NOW)

Read `../../IDEA_SCOPE.md` §10 (demo contract) and `../../CLAUDE.md` first.

## Mission
The judge sees this screen for 2 minutes. **The blocking-edges panel is the hero** —
if the plan reads as a flat to-do list, Creativity collapses to L2 and we lose 4.5
weighted points. Your job is to make the *dependency* the most visible thing on screen.

## Files you own
`web/` only. **Forbidden:** everything in `src/`, `tests/`, `fixtures/`.

You need no API key. `POST /api/case/fixture/demo` already returns a full plan.

## Priorities in order

### 1. Make blocking visible (Creativity — highest value)
Today edges are a text list in a side panel. Make the relationship *graphic*:
- Draw the chain **O1 → O2 → O3** as connected cards or a simple left-to-right
  rail, with the blocked ones visibly downstream and greyed.
- On each blocked card, print the quoted reason **inline on the card**, not in a
  separate panel: `🔒 blocked by O1 — "Name of applicant must match record-of-rights entry exactly"`
- Show the source doc name next to every quote.
- A judge glancing for 3 seconds must see: *one thing is doable, the others are waiting on it, and here's the sentence that says so.*

### 2. The "DO THIS FIRST" banner
Make it unmissable — biggest element on the page, with the required documents listed
under it. This is the product's whole promise.

### 3. Escalation panel (Delight)
`plan.refusals` → show `source.crop_path` as an `<img>` when present (feat/register
generates these). Copy should read like honest judgment, not an error:
> ✋ **Area column — cannot be read safely.** A seal covers part of this figure.
> Routed to human review. *Re-photograph this page straight-on in daylight to resolve.*

The rest of the analysis must stay visible — never blank the screen on a refusal.

### 4. Live re-sequence (JTBD)
When "Mark record corrected ✓" is clicked, the re-render should be *visibly* a
re-sequence — brief highlight/transition on the item that becomes actionable.

### 5. Upload flow
Drag-and-drop with thumbnails and a processing state per file. Handle the `501`
gracefully until feat/extraction lands (it already does — keep that).

## Constraints
- **Single file `web/index.html`, no build step, no CDN.** Vanilla JS + inline CSS.
  A broken import at 4pm loses the event.
- Must work at 1280×720 (projector). Test at that size.
- Don't rename API routes or response fields.

## Acceptance test
> A first-time viewer, given only the screen, can say out loud which item to do
> first and why the second item cannot start yet — without the presenter explaining.

---

# ADDENDUM (14:10) — API has grown since this brief was written

`feat/sequencer` and `feat/case-memory` are **merged into main**. `git merge main`
first. 34 tests are green. New material you should render:

## New/changed endpoints

| Method | Path | What's new |
|---|---|---|
| GET | `/api/cases` | **new** — list rows: `id, created, updated, item_count, next_single_action, refusal_count, correction_count` |
| POST | `/api/case/{id}/reset` | **new** — back to as-loaded state. **Wire this to a Reset button; M5 needs it for repeated demo runs.** |
| GET | `/api/case/{id}` | now also returns `created`, `updated`, `correction_log[]` |
| POST | `/api/case/{id}/correct` | now also returns `last_correction` and a rich **`diff`** |

## The `diff` object is your Memory evidence — render it

`diff.summary` is **one printable sentence, already written for the screen**. Print
it verbatim. Example:

> `owner_name on record_page_1947: 'Sushila D.' → 'SUSHILA DEVI' — cleared the O1↔O2 cosmetic mismatch on owner_name. Next single action unchanged`

Under it, list `diff.obligations[].changes`. Also useful: `diff.mismatches_cleared`,
`diff.refusals_cleared`, `diff.edges_removed`, `diff.propagated_to`.

**Honest detail that matters:** correcting the name does **not** unblock O2 — that
needs the mock status lookup. The demo beat is two steps: *correct → mismatch clears
and propagation is listed*, **then** *mark-done → re-sequences*. Don't design a UI
that implies the correction alone unblocked it.

A bad correction target returns **404** with an `available_targets[]` menu — show
that menu instead of a raw error toast.

## Sequencer behaviour you must not break

- `next_single_action` is **never null** now. When nothing can be started it carries
  an honest sentence naming the missing keys. **Render that sentence in the
  DO-THIS-FIRST banner** — do not treat it as an error or blank the banner.
- Dependency cycles are broken deterministically; the waived edge is still emitted
  as a `BlockingEdge`. So an item can be `actionable` *and* appear in `plan.edges`.
  Don't assume actionable ⇒ no edges.

## Priority order given the clock (~1h of useful build left)

1. **Blocking chain visible, quoted reason inline on the card** ← Creativity, do first
2. DO-THIS-FIRST banner unmissable (handle the honest-sentence case)
3. Refusal panel: show `source.crop_path` as `<img>` when present, honest copy
4. `diff.summary` after a correction
5. Reset button → `POST /api/case/{id}/reset`

Anything below 5 is parking lot. Do not start a redesign.

## Verify
```bash
py -3.12 -m pytest -q                          # 34 must stay green
py -3.12 -m uvicorn src.app:app --port 8000
```
Merge after `feat/register` (or before it if register is running late — coordinate
with main).
