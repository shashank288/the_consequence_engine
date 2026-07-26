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

## Verify
```bash
py -3.12 -m uvicorn src.app:app --port 8000
```
Merge after `feat/register`.
