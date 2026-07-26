# HANDOFF — feat/sequencer (M2 hardening)

**Status:** brief complete, gate green, **not pushed, no PR**.
**Commit:** `0cc3383` on `feat/sequencer` (branch has no upstream; `origin/main` still `f3eb0b6`).
**Gate:** `.\scripts\verify.ps1` → PASSED — 22 tests (2 original + 20 new), fixture golden
path byte-identical, `src/contracts.py` untouched.

---

## 1. What shipped

| # | Change | Failure it prevents on stage |
|---|---|---|
| 1 | **Cycle safety** — loops (incl. self-loops) detected, broken by earliest ISO deadline then lowest id; the waived dependency is still emitted as a `BlockingEdge` quoting both pages and stays in the item's `needs_docs` | Two mutually blocked items and a blank "NEXT SINGLE ACTION" |
| 2 | **Never-silent plan** — when nothing is startable, `next_single_action` carries an honest sentence naming the missing keys instead of `None` | Screen reads "nothing to do" when the truth is "nothing can be started" |
| 3 | **Transitive chains** — verified 4-deep; completing the root unblocks exactly one step per status update | Mark-blocker-done releasing the whole chain at once |
| 4 | **Duplicate robustness** — asker matched by token-subset after org-noise stripping; ask similarity drops stopwords + folds plurals; Jaccard floor guards over-merge; a folded duplicate's `needs`/`provides` are absorbed by the kept item | SMS not folding into the bank letter; or worse, two real obligations silently collapsing into one |
| 5 | **Script-aware mismatches** — case/spacing-only → cosmetic; N readings judged pairwise on the **worst** verdict; Devanagari↔Latin compared by consonant skeleton | The old ASCII-only normaliser erased all Devanagari, so two *different* Hindi names compared equal and no mismatch was raised at all |
| 6 | **Date normalisation** — `14/08/2026`, `01.09.2026`, `14 Aug 2026`, `30th September 2026`, `14/08/26` → ISO; day-first for ambiguous numerics; impossible dates rejected; unreadable/refused deadlines sort undated | Ordering on raw text ("01.09.2026" sorting before "14/08/2026") |

**Files:** `src/sequencer/core.py` (hardened, not rewritten), new `src/sequencer/dates.py`,
new `src/sequencer/text.py`, new `tests/test_sequencer_hardening.py`. Nothing outside branch ownership.

## 2. Reusable helpers other branches may import

Pure functions, no I/O, no key needed. **feat/register** in particular should not re-derive these:

| Import | Use |
|---|---|
| `src.sequencer.text.cross_script_verdict(a, b)` | Devanagari↔Latin name comparison → `("cosmetic"\|"unknown", reason)`. Never returns cosmetic without a skeleton match — use it for the card-87 contradiction check against the mocked prior record |
| `src.sequencer.text.office_relation(a, b)` | `"same"\|"different"\|"unknown"` for two asker strings |
| `src.sequencer.text.norm(s)` / `content_tokens(s)` | Script-safe normalisation (keeps Devanagari + combining marks) |
| `src.sequencer.dates.to_iso(s)` | Any page date → ISO, or `None` when unreadable |

## 3. Verified vs assumed — read before planning

- **Verified:** all logic above, against staged + synthetic-messy cases I authored.
- **NOT verified:** behaviour on *real* extractor output. `feat/extraction` doesn't exist yet, so
  IDEA_SCOPE §8's M2 acceptance — "test_sequencer.py **+ a real-set run** shows edge with quote +
  duplicate + unknown" — is only half done. The second half is gated on extraction merging.

## 4. Decisions I made that you can reverse

| Decision | Where | Reverse if |
|---|---|---|
| Dup thresholds: containment ≥0.6 **and** Jaccard ≥0.4 (same asker); ≥0.85/≥0.7 (unknown asker) | `core.py` top | Real SMS/letter pairs stop folding — raise/lower here, not in the matcher |
| Ambiguous numeric dates read **day-first** (Indian convention) | `dates.py` | A doc set turns out to be US-formatted |
| Cross-script non-match → `unknown`, never `blocking` | `text.py` | You want louder alarms; risk is false blocking edges on stage |
| Folded duplicates donate `needs`/`provides` to the kept item | `core.py::_absorb` | It ever over-blocks; under-blocking is the more dangerous direction |
| Cycle breaker becomes `actionable` with the loop shown as an edge | `core.py::_break_cycles` | You'd rather show all loop members blocked + honest statement |

## 5. Suggested next steps

1. **Nothing to do until `feat/extraction` lands** — merge order is extraction → sequencer.
2. When it lands: rebase on main, run `verify.ps1`, then a real-set run. Watch these first:
   - asker strings noisier than `ORG_NOISE` in `text.py` (add tokens there, not new logic)
   - Hindi `asked_what` text shifting duplicate scores (now scores at all — previously always 0.0)
   - extractor emitting a need whose key nothing provides → item blocks forever; that is correct
     behaviour and now produces the honest statement, but check the wording reads well on screen
3. Push + PR when you want it queued: `git push -u origin feat/sequencer`.

## 6. Open decision for the scope owner

**Actionable items are still ordered by deadline alone.** IDEA_SCOPE §1's creativity thesis says
"sorting by deadline is wrong by design"; ranking by *how many items an action unblocks* (deadline
as tie-break) would demo that thesis directly. I left it out — it changes visible demo ordering and
was not in the brief. ~20 lines + 2 tests if you want it. **Your call.**

## 7. Parking lot (not built, deliberately)

- Unblock-count ordering (§6 above)
- A staged `fixtures/case_cycle.json` so the UI can demo a loop without real data
- Confidence-weighted mismatch severity (a 0.76 read and a 0.99 read treated identically today)

## 8. Run

```bash
py -3.12 -m pytest -q             # 22 green, no key needed
py -3.12 -m scripts.run_case      # golden path
.\scripts\verify.ps1              # the gate
```
