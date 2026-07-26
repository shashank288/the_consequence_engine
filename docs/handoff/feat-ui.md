# HANDOFF — feat/ui (judge-facing screen · the blocking chain is the hero)

| Field | Value |
|---|---|
| Branch | `feat/ui` |
| Commit | `11b4946` (2026-07-26 14:50 IST) — committed, **not pushed** |
| Handoff written | 2026-07-26 14:57 IST |
| Status | **Verified** — acceptance test passes; `.\scripts\verify.ps1` green (34 passed · golden path ok · contract untouched) |
| Merge position | after `feat/register`, before `feat/voice` |
| Rubric | Creativity ×1.5 — the dependency must not read as a flat to-do list |
| Needs a Sarvam key? | **No.** `POST /api/case/fixture/demo` drives the whole screen offline. |
| Files touched | `web/index.html` only (single file, +handoff doc) |

Read with: `docs/agents/feat-ui.md` (the brief + its 14:10 addendum), `IDEA_SCOPE.md` §10
(demo contract).

**Acceptance test — met.** A first-time viewer, given only the screen, can say which item to do
first (one green card, one banner) and why the second cannot start (a quoted sentence printed on
the card, naming the page it came from).

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

## 2. Addendum items

| # | Item | Status |
|---|---|---|
| 1 | Blocking chain visible, quote inline | done — §1 |
| 2 | DO-THIS-FIRST banner, honest-sentence case | done — §4 |
| 3 | Refusal panel with `source.crop_path` | done — §5 |
| 4 | `diff.summary` after a correction | done — Memory panel, printed verbatim |
| 5 | Reset button → `POST /api/case/{id}/reset` | done — header, enabled once a case is loaded |

Also wired (cheap, and it is the reload-resume evidence): a **`Resume saved case…`** select fed by
`GET /api/cases`, showing `id · items · refused · corrections`. Picking one calls
`GET /api/case/{id}` and re-renders, then lists `correction_log[]` — proving the plan and its
corrections survive a fresh process. Nothing below addendum priority 5 was started; no redesign.

## 3. The 2-minute demo, click by click

```
py -3.12 -m uvicorn src.app:app --port 8000     →  http://localhost:8000
```

| # | Click | What to say / what appears |
|---|---|---|
| 1 | **Load demo case** | Banner + rail fill. *"One thing is doable. Two are waiting on it, and the page says why."* |
| 2 | *(point, don't click)* the O2 card | The quoted requirement, its source page, and the O1 → O2 connector labelled `needs record_name_matches_id`. |
| 3 | *(hover)* `blocked by O1` on O2 | O1 lights up in the rail — the relation, not just a label. |
| 4 | **Correct → propagate** (prefilled `record_page_1947 / owner_name / SUSHILA DEVI`) | Memory panel opens, prints `diff.summary` verbatim; O1 and O2 pulse blue. **Say the honest line the screen already says: this did not unblock O2.** |
| 5 | **Mark record corrected ✓** | O1 → done, O2 → actionable with `START HERE`, both flash green `↻ re-sequenced`, banner rewrites to the O2 action and its 2026-08-14 deadline. |
| 6 | *(point)* Escalation queue | `plot_area` refused at 0.55 — routed, not guessed, with the page and the words on it. |
| 7 | **⟲ Reset case** | Back to as-loaded. Safe to run the whole thing again for the next judge. |

Steps 4 and 5 are deliberately two beats. Do not compress them — see §4.

## 4. Sequencer behaviour the UI respects

- **`next_single_action` is never null.** When no item is actionable the banner does not blank
  and does not read as an error: it flips to an amber variant, `⛔ Nothing can be started yet —
  here is why`, prints the honest sentence verbatim, and adds *"This is a refusal to guess, not
  a failure to read."* Exercised against a synthetic all-blocked plan.
- **actionable ⇏ no edges.** A deterministically waived cycle edge renders as an amber
  `⚠ waived loop with O1` block carrying the full `_cycle_reason` sentence, not a red lock — the
  card stays green and startable. Exercised against a synthetic actionable-with-edge plan.
- **The correction does not unblock O2, and the UI says so.** The Memory panel prints
  `diff.summary` verbatim, then `diff.obligations[].changes` per obligation, then chips for
  `mismatches_cleared / refusals_cleared / edges_removed / edges_added / propagated_to`.
  If nothing went `blocked → actionable` it prints: *"No item became startable from this
  correction alone — the record still has to be filed and the tehsil status confirmed."*
  That sentence is derived from the diff, not hardcoded: when an item **does** cross to
  actionable it names it instead. The two-step demo beat stays honest either way.
- **A bad correction target renders the menu, not a toast.** The 404's
  `detail.available_targets[]` becomes a clickable list (`doc_id · field = "value" (O2, read)`);
  clicking one fills the correction inputs.

## 5. Refusals / crops — one thing still open for feat/register

Refusals render with the crop as an `<img>`, honest copy ("Read at 0.55 confidence, below the
refusal threshold. Routed to human review — not guessed, not silently dropped"), the source
page and its quote, and the fix instruction. The rest of the analysis stays on screen.

**The demo fixture's `crop_path` is `fixtures/crops/plot_area.png`, which does not exist on disk
and would not be served if it did** — `src/app.py` mounts only `web/` at `/`. The UI degrades in
two steps rather than breaking: it retries `/crops/<basename>` (i.e. `web/crops/`, which *is*
served, and which CLAUDE.md assigns to feat/register), then falls back to a
`🔍 field crop not published` placeholder.

**To make the seal crop actually appear:** feat/register writes the crop to
`web/crops/plot_area.png`. No UI change needed — the retry already points there. Alternatively
main points the fixture's `crop_path` at `crops/plot_area.png`. Not fixable from this branch:
both files are out of scope.

## 6. Re-sequence feedback

`markDone` diffs each item's previous state and flashes a green pulse + `↻ re-sequenced` tag on
items that became actionable or done — so the O1→O2 handoff reads as a re-sequence, not a
re-paint. Corrections use a distinct blue `↺ updated` pulse on `diff.propagated_to`, keeping
"memory propagated" visually separate from "plan moved".

## 7. API surface this screen consumes

Rename any of these and the screen degrades. Nothing else in `web/` is depended on.

| Endpoint | Fields read |
|---|---|
| `POST /api/case/fixture/demo` | `id`, `drafts[].{id,doc_id,asked_what,asked_by,due,identity_fields,raw_excerpt}`, `plan` |
| `GET /api/cases` | `id`, `item_count`, `refusal_count`, `correction_count` |
| `GET /api/case/{id}` | as above + `correction_log[].diff.summary` |
| `POST /api/case/{id}/reset` | full case |
| `POST /api/case/{id}/status/{key}` | full case |
| `POST /api/case/{id}/correct` | `diff.{summary,propagated_to,obligations,mismatches_cleared,refusals_cleared,edges_removed,edges_added}`, `last_correction.propagated_to`; on 404 `detail.available_targets[]` |
| `POST /api/case` | `501` → falls back to the demo case; real response renders through the same `render()` unchanged |
| `plan.*` | `items[].{obligation_id,state,order,duplicate_of,next_action,needs_docs}`, `edges[].{blocked_id,blocker_id,need_key,reason,evidence[].{doc_id,page,quote}}`, `mismatches[]`, `refusals[].{name,confidence,source.{doc_id,page,quote,crop_path}}`, `next_single_action` |

## 8. Constraints held

Single file, vanilla JS, inline CSS, **no build step, no CDN, no imports**. All user-visible
values pass through an `esc()` HTML-escaper (the fixture carries Devanagari and quote
characters). No API route or response field renamed; `src/`, `tests/`, `fixtures/`, `scripts/`
untouched. Laid out for 1280×720 — banner + full rail sit above the fold; three 296px cards
plus connectors span ~1030px, and the rail scrolls horizontally beyond that.

## 9. How it was verified

- `.\scripts\verify.ps1` → `34 passed` · `ok: next action + blocking edge + refusal all present`
  · `ok: contract untouched` · **VERIFY PASSED**.
- `node --check` on the extracted inline script — parses clean.
- No browser tooling was available in the build session, so `render()` was replayed in Node
  against **live API responses** with a DOM stub, across six scenarios: fresh load,
  post-correction, 404 target menu, post-mark-done re-sequence, synthetic all-blocked plan,
  synthetic actionable-with-edge plan. Emitted HTML was asserted free of `undefined` / `NaN` /
  escaping artifacts, and card order, connector labels, inline quotes and reason tails were
  checked against the fixture's actual values.
- **Not machine-verified: pixel layout.** The 1280×720 fit is arithmetic (296px cards +
  connectors ≈ 1030px) plus CSS overflow, not a screenshot. Worth one human glance on the
  projector before submission — it is the only unverified claim in this document.

## 10. Notes for whoever merges

- Merge order per CLAUDE.md puts `feat/register` first; this branch does not depend on it to
  render (the crop degrades, §5), so it can merge either side if register runs late.
- Upload still falls back to the demo case on `501`; when feat/extraction lands, its response
  renders through the same `render()` with no change here.
- `docs/agents/feat-ui-conclusion.md` is an **untracked, stale** note from an earlier pass — it
  claims "2 passed" and a `verify.ps1` encoding blocker. Both are obsolete: verify passes at 34
  tests today. Deleted or ignored, either is fine; it was deliberately not committed.
- The verification harness lives in the session scratchpad, not the repo — no test files were
  added, per branch ownership (`tests/` belongs to main).
