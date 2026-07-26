# Handoff — feat/ui

**Branch:** `feat/ui` · **Owns:** `web/` only · **Files changed:** `web/index.html` (single file)
**Date:** 2026-07-26 · **Merge order:** after `feat/register`, before `feat/voice`

Verified against a live server (`py -3.12 -m uvicorn src.app:app --port 8000`) on real
`POST /api/case/fixture/demo` responses. `.\scripts\verify.ps1` → **34 passed, golden path ok,
contract untouched, VERIFY PASSED**.

---

## 1. What a judge sees, in the order they see it

**Banner — DO THIS FIRST.** Biggest element on the page. Prints `plan.next_single_action`
verbatim, the office it is owed to, the stated deadline when one was *read*, the papers to
carry, and `Completing O1 unblocks O2 → O3`.

**The rail — the hero.** `plan.items` are laid out left-to-right by real dependency depth as
connected cards, `O1 ▶ O2 ▶ O3`. The actionable card is the only bright thing on screen
(green, glowing, `START HERE` pill); blocked cards are downstream, greyed and desaturated.

**The connector is labelled with the requirement key** that ties the two cards together —
`O1 ──needs record_name_matches_id──▶ O2`, with the bar running green→red into a blocked
card and solid green (`requirement satisfied`) once the blocker is done. The dependency is
readable as a graph without touching anything.

**The quoted reason is printed inline on each blocked card**, not in a side panel:

```
🔒 blocked by O1   [record_name_matches_id]
   “Name of applicant must match record-of-rights entry exactly”
   source: counter_slip · p1
   also evidenced on record_page_1947, aadhaar_heir     (hover → the exact words on each)
   required by Tehsil office, Khammam; not yet satisfied
```

Hovering `blocked by O1` highlights the O1 card in the rail, so the pair reads as one relation.
Every quote carries its source doc name and page. The trailing sentence is the tail of the
sequencer's own `edge.reason` — nothing is authored in the UI.

**Acceptance test met:** the screen alone says which item to do first (one green card, one
banner) and why the second cannot start (a quoted sentence, on the card, naming its page).

## 2. Addendum items

| # | Item | Status |
|---|---|---|
| 1 | Blocking chain visible, quote inline | done — see above |
| 2 | DO-THIS-FIRST banner, honest-sentence case | done — see §3 |
| 3 | Refusal panel with `source.crop_path` | done — see §4 |
| 4 | `diff.summary` after a correction | done — Memory panel, printed verbatim |
| 5 | Reset button → `POST /api/case/{id}/reset` | done — header, enabled once a case is loaded |

Also wired (cheap, and it is the reload-resume evidence): a **`Resume saved case…`** select fed by
`GET /api/cases`, showing `id · items · refused · corrections`. Picking one calls
`GET /api/case/{id}` and re-renders, then lists `correction_log[]` — proving the plan and its
corrections survive a fresh process.

## 3. Sequencer behaviour the UI respects

- **`next_single_action` is never null.** When no item is actionable the banner does not blank
  and does not read as an error: it flips to an amber variant, `⛔ Nothing can be started yet —
  here is why`, prints the honest sentence verbatim, and adds *"This is a refusal to guess, not
  a failure to read."* Exercised against a synthetic all-blocked plan.
- **actionable ⇏ no edges.** A deterministically waived cycle edge renders as an amber
  `⚠ waived loop with O1` block with the full `_cycle_reason` sentence, not a red lock — the
  card stays green and startable. Exercised against a synthetic actionable-with-edge plan.
- **The correction does not unblock O2, and the UI says so.** The Memory panel prints
  `diff.summary` verbatim, then `diff.obligations[].changes` per obligation, then chips for
  `mismatches_cleared / refusals_cleared / edges_removed / edges_added / propagated_to`.
  If nothing went `blocked → actionable` it prints: *"No item became startable from this
  correction alone — the record still has to be filed and the tehsil status confirmed."*
  That sentence is derived from the diff, not hardcoded: when an item **does** cross to
  actionable it names it instead. The two-step demo beat stays honest.
- **A bad correction target renders the menu, not a toast.** The 404's
  `detail.available_targets[]` becomes a clickable list (`doc_id · field = "value" (O2, read)`);
  clicking one fills the correction inputs.

## 4. Refusals / crops — one thing still open for feat/register

Refusals render with the crop as an `<img>`, honest copy ("Read at 0.55 confidence, below the
refusal threshold. Routed to human review — not guessed, not silently dropped"), the source
page and its quote, and the fix instruction. The rest of the analysis stays on screen.

**The demo fixture's `crop_path` is `fixtures/crops/plot_area.png`, which does not exist on disk
and would not be served if it did** — `src/app.py` mounts only `web/` at `/`. The UI degrades in
two steps rather than breaking: it retries `/crops/<basename>` (i.e. `web/crops/`, which *is*
served, and which CLAUDE.md assigns to feat/register), then falls back to a
`🔍 field crop not published` placeholder.

**To make the seal crop actually appear:** feat/register writes the crop to `web/crops/plot_area.png`.
No UI change needed — the retry already points there. Alternatively main can point the fixture's
`crop_path` at `crops/plot_area.png`. Not fixable from this branch: both files are out of scope.

## 5. Re-sequence feedback

`markDone` diffs each item's previous state and flashes a green pulse + `↻ re-sequenced` tag on
items that became actionable or done — so the O1→O2 handoff reads as a re-sequence, not a
re-paint. Corrections use a distinct blue `↺ updated` pulse on `diff.propagated_to`, keeping
"memory propagated" visually separate from "plan moved".

## 6. Constraints held

Single file, vanilla JS, inline CSS, **no build step, no CDN, no imports**. All user-visible
values pass through an `esc()` HTML-escaper (the fixture carries Devanagari and quote
characters). No API route or response field renamed; `src/`, `tests/`, `fixtures/`, `scripts/`
untouched. Laid out for 1280×720 — banner + full rail sit above the fold; three 296px cards
plus connectors span ~1030px, and the rail scrolls horizontally beyond that.

## 7. Notes for whoever merges

- Upload still falls back to the demo case on `501`; when feat/extraction lands, its response
  renders through the same `render()` with no change here.
- `docs/agents/feat-ui-conclusion.md` is an **untracked, stale** note from an earlier pass — it
  claims "2 passed" and a `verify.ps1` encoding blocker. Both are obsolete: verify passes at 34
  tests today. Deleted or ignored, either is fine; it was deliberately not committed.
- Verification harness used (DOM-stubbed replay of `render()` against live API responses) lives
  in the session scratchpad, not the repo — no test files were added, per branch ownership.
