# HANDOFF — feat/case-memory (M4 · Memory & Context)

| Field | Value |
|---|---|
| Branch | `feat/case-memory` |
| Commit | `da479fb` (2026-07-26 13:25 IST) |
| Handoff written | 2026-07-26 13:40 IST |
| Status | **Verified** — acceptance test passes; `.\scripts\verify.ps1` green (14 passed · golden path ok · contract untouched) |
| Merge position | after `feat/register`, before `feat/ui` |
| Rubric | Memory & Context ×1 → **L4** (persisted, governed continuity) |
| Needs a Sarvam key? | **No.** Every test and the fixture golden path run offline. |

Read with: `docs/agents/feat-case-memory.md` (the brief), `IDEA_SCOPE.md` §3 memory
boundary / §6 rubric row / §8 M4.

---

## 1. What shipped

Brief tasks 1–3 complete. Task 4 (stale-vs-current) deliberately NOT started — its
own gate says "do not start until 1–3 are merged".

| # | Task | Where |
|---|---|---|
| 1 | Correction propagation, `propagated_to` computed by diffing the plan | `src/case_store/corrections.py` |
| 2 | Resume after reload (fresh process → identical plan) | `src/case_store/store.py` |
| 3 | `GET /api/cases`, `POST /api/case/{id}/reset` | `src/app.py` |

**Files touched (nothing outside the brief's ownership):**

```
src/case_store/__init__.py     public surface, re-exports
src/case_store/store.py        NEW  persistence + baseline + meta sidecar
src/case_store/corrections.py  NEW  patch → re-sequence → diff
tests/test_memory.py           NEW  12 tests
src/app.py                     correct, get_case + 2 new routes (task 3)
.env.example                   key scrubbed to a placeholder (see §7)
```

`src/contracts.py` untouched — the whole feature works inside the FROZEN contract.

---

## 2. Public surface (import from `src.case_store`)

```python
load_case(case_id) -> Case | None          # signature FROZEN, unchanged
save_case(case) -> None                    # signature FROZEN, unchanged
list_cases() -> list[dict]                 # id, created, updated, item_count,
                                           # next_single_action, refusal_count,
                                           # correction_count
reset_case(case_id) -> Case | None         # back to as-loaded state, plan re-derived
case_meta(case_id) -> dict                 # created / updated / correction_log / reset_count
log_correction(case_id, entry) -> None
apply_correction(case, doc_id, field_name, new) -> (Case, Correction, diff)
correction_targets(case) -> list[dict]     # every correctable (doc_id, field_name)
diff_plans(case, before, after) -> dict    # reusable: also describes status-lookup moves
CaseStore(path=None)                       # explicit-path instance, for tests
CorrectionTargetNotFound, CaseStoreError
```

`apply_correction` mutates the case (drafts, `plan`, `corrections`) and returns it;
**the caller persists** (`save_case`). It is pure logic — no I/O, no network.

---

## 3. HTTP API

| Method | Path | Notes |
|---|---|---|
| POST | `/api/case/fixture/{name}` | unchanged (baseline snapshot is captured on this first save) |
| GET | `/api/cases` | **new** — one row per case, see §2 |
| GET | `/api/case/{id}` | case dump **+** `created`, `updated`, `correction_log` |
| POST | `/api/case/{id}/reset` | **new** — as-loaded state, returns the case dump |
| POST | `/api/case/{id}/correct` | case dump **+** `last_correction` **+** `diff` |
| POST | `/api/case/{id}/status/{key}` | unchanged (owned by main) |

### `POST /api/case/{id}/correct`

Request: `{"doc_id": "...", "field_name": "...", "new": "..."}` → 422 if any is missing.

Unknown target → **404**, refused rather than recorded as a no-op:

```json
{"detail": {"error": "no 'owner_name' reading sourced from doc 'counter_slip'",
            "available_targets": [{"doc_id": "aadhaar_heir", "field_name": "owner_name",
                                   "obligation_id": "O2", "current_value": "SUSHILA DEVI",
                                   "status": "read"}, ...]}}
```

Success response is the full case dump plus:

```json
{
  "last_correction": {"doc_id": "record_page_1947", "field_name": "owner_name",
                      "old": "Sushila D.", "new": "SUSHILA DEVI",
                      "propagated_to": ["O1", "O2"]},
  "diff": {
    "propagated_to": ["O1", "O2"],
    "obligations": [
      {"obligation_id": "O2", "changes": ["evidence for the O1 → O2 edge changed (record_name_matches_id)",
                                          "owner_name mismatch resolved"],
       "state_before": "blocked", "state_after": "blocked",
       "order_before": null, "order_after": null}
    ],
    "mismatches_cleared": [{"field_name": "owner_name", "classification": "cosmetic",
                            "values": ["Sushila D.", "SUSHILA DEVI"],
                            "obligations": ["O1", "O2"]}],
    "mismatches_added": [], "mismatches_reclassified": [],
    "edges_added": [], "edges_removed": [],
    "refusals_cleared": [], "refusals_added": [],
    "next_single_action_before": "File record-correction application ...",
    "next_single_action_after":  "File record-correction application ...",
    "patched_readings": [{"obligation_id": "O1", "doc_id": "record_page_1947",
                          "field_name": "owner_name", "old": "Sushila D.",
                          "old_status": "read", "old_confidence": 0.81,
                          "new": "SUSHILA DEVI"}],
    "plan_summary": "cleared the O1↔O2 cosmetic mismatch on owner_name. Next single action unchanged",
    "summary": "owner_name on record_page_1947: 'Sushila D.' → 'SUSHILA DEVI' — cleared the O1↔O2 cosmetic mismatch on owner_name. Next single action unchanged"
  }
}
```

**For `feat/ui`:** the existing `web/index.html` keeps working untouched — the response
is still a case dump and `corrections[-1].propagated_to` is still there. To upgrade the
panel, print `diff.summary` verbatim (one printable sentence, already built for the
screen) and list `diff.obligations[].changes` under it. `GET /api/case/{id}` →
`correction_log[]` (`{at, correction, diff}`) gives the same material after a reload.

---

## 4. How propagation is computed (why it is trustworthy)

1. `before = build_plan(case)` — re-derived from current drafts, so the diff isolates
   **this** correction and cannot inherit a stale stored plan.
2. Patch **every** reading whose `name == field_name` and whose **doc of record** is
   `doc_id`, where doc of record = `source.doc_id` if present, else the draft's `doc_id`.
   Patched readings become `status="read"`, `confidence=1.0` (human-confirmed).
3. `after = build_plan(case)`.
4. Fingerprint each obligation in both plans — `state`, `order`, `duplicate_of`,
   `needs_docs`, `next_action`, blocking edges **including evidence refs**, mismatches
   it participates in (classification + readings + participants), refused field names.
5. `propagated_to` = obligations whose fingerprint changed. Nothing is guessed, and the
   old doc-id sweep (which claimed any obligation whose edge merely cited the doc) is gone.

**Consequences worth knowing:**

- Correcting `owner_name` on `record_page_1947` reaches **O1 and O2** — O1 carries the
  patched reading, O2's blocking edge loses its mismatch evidence. O3/O4 are **not**
  claimed. There is a regression test for that non-over-claiming.
- **The correction does NOT unblock O2.** O2 needs `record_name_matches_id`, which only
  the mock status lookup satisfies. The summary says so honestly
  ("Next single action unchanged"). The demo beat is: correct → mismatch clears +
  propagation list; *then* mark-done → re-sequence. `diff_plans` emits
  `"unblocked O2"` for that second step (tested).
- O2's `owner_name` was read off `aadhaar_heir`, not off `counter_slip` — correcting it
  needs `doc_id: "aadhaar_heir"`. Typing `counter_slip` returns the 404 menu above.
- A refused reading still holds its sub-threshold value in the draft (the refusal happens
  in the plan, on the sequencer's copy). So `Correction.old` is that superseded value
  (e.g. `plot_area` `"2 acre 13 gunta"` @ 0.55), with `old_confidence` in
  `patched_readings` — the raw material task 4 will need.
- Correcting `plot_area` drains the escalation queue: `plan.refusals == []` and
  `diff.refusals_cleared` names it. Cheap second Memory/Delight beat if wanted.

---

## 5. Storage format

`CASE_DB` (default `cases.json`, resolved against the repo root, overridable per process
— tests point it at `tmp_path`). One file, one envelope per case:

```json
{"version": 2,
 "cases": {"<case_id>": {"case":     { ...Case... },
                         "meta":     {"created", "updated", "correction_log": [], "reset_count"},
                         "baseline": { ...Case as first saved... }}}}
```

- `baseline` is captured on the **first** `save_case` for that id (i.e. straight after
  fixture load / extraction) and is what `reset_case` restores, with the plan re-derived.
- `meta` carries the continuity the FROZEN `Case` contract has no field for — no
  `CONTRACT-CHANGE` PR was needed.
- Writes are atomic (`tmp` + `os.replace`), so a killed process cannot leave a half-written
  case DB mid-demo. Corrupt JSON raises `CaseStoreError` rather than silently overwriting.
- A legacy flat `{case_id: case_dump}` file (the lite store on main) is migrated on read;
  the next save writes v2. Tested.
- Every read hits disk — that is the reload-resume proof, and why `GET` after a restart
  serves the identical plan. SQLite stays in the parking lot (IDEA_SCOPE §13).

---

## 6. Tests · verification

```bash
py -3.12 -m pytest -q          # 14 passed (2 sequencer + 12 memory)
.\scripts\verify.ps1           # tests + fixture golden path + frozen-contract check
```

`tests/test_memory.py` covers: propagation + mismatch clearing, non-over-claiming,
refusal resolution, doc-of-record targeting (`aadhaar_heir`), refused unknown target,
status-lookup re-sequence reporting, reload-resume in a fresh store, corrected state +
diff surviving reload, legacy file migration, `list_cases`, `reset_case`, and one HTTP
round trip (correct → GET → bad correct → list → reset → 404s → 422).

`CASE_DB` is redirected to `tmp_path` by an autouse fixture — tests never touch the real
`cases.json`.

**Acceptance test, verified live:**

```
correct owner_name @ record_page_1947 → "SUSHILA DEVI"
  summary : owner_name on record_page_1947: 'Sushila D.' → 'SUSHILA DEVI'
            — cleared the O1↔O2 cosmetic mismatch on owner_name. Next single action unchanged
  prop_to : ['O1', 'O2']
  reload  : fresh store → mismatches [], owner_name conf 1.0, correction + diff persisted
```

---

## 7. Secrets — current state

- `.env.example` is now committed **with an empty `SARVAM_API_KEY=`** placeholder plus
  run instructions. No key in any tracked file.
- The real key lives only in local, gitignored `.env` files (`.gitignore:1`). `.env` is
  **per worktree** and is currently present only in `ce-worktrees/case-memory`; the
  worktree that actually needs it is `ce-worktrees/extraction`.
- ⚠️ **The key is still in git history** — it was committed inside `.env.example` in
  `dddebe2` and `f3eb0b6`, and both are on `origin`. Scrubbing the working tree does not
  remove it. **Rotate the key after the event** (or now, and re-fill the local `.env`).
- ⚠️ **Nothing in the code calls `load_dotenv()`.** `src/config.py` reads bare
  `os.getenv`, so `.env` reaches the app only via
  `py -3.12 -m uvicorn src.app:app --port 8000 --env-file .env`
  (`python-dotenv` ships with `uvicorn[standard]`, so this works today). Bare `uvicorn`,
  `pytest` and `scripts.run_case` will not see it — harmless for those, since none need a
  key. Adding the loader means editing `config.py`, which main owns: **not done here.**

---

## 8. Merging this branch

1. `git rebase main` (merge order: extraction → sequencer → register → **case-memory** → ui → voice).
2. `.\scripts\verify.ps1` must be green.
3. Expected conflicts: **`src/app.py` only** — the import block at the top and the
   `correct` / `get_case` bodies. Resolution rule: keep this branch's versions of
   `correct`, `get_case`, `list_all_cases`, `reset`, and keep the other branch's
   `create_from_uploads` / `mark_done` / `create_from_fixture`.
4. `src/case_store/` and `tests/test_memory.py` are new files — no conflicts expected.
5. If `feat/extraction` starts saving cases before planning, `reset_case` still works
   (it re-derives the plan from the baseline drafts).

---

## 9. Open dependencies (NOT this branch's work)

| Item | Owner | Effect on this feature |
|---|---|---|
| Handwritten register page + crop images | `feat/register` / inputs — being sorted, "we will figure it out" | none: this feature is doc-agnostic. `fixtures/case_demo.json` points `plot_area.crop_path` at `fixtures/crops/plot_area.png`, which does not exist yet, so the refusal renders with its quote but no image. Correction/propagation over that same field is fully wired and tested. |
| `POST /api/case` (real photo → drafts) | `feat/extraction` (stub, `501`) | none: corrections work on any `Case`, whatever produced it. Whichever path creates the case, its **first save is the reset baseline**. |
| Rendering `diff.summary` / `correction_log` | `feat/ui` | optional upgrade; the current UI already works unchanged. |
| `load_dotenv()` in `config.py`, key rotation | main / Shashank | §7 |

## 10. Follow-ups for this feature (in priority order)

1. **Task 4 — stale vs current (L5 language).** Keep a superseded reading visible instead
   of overwriting it. The material is already persisted: `Correction.old`,
   `patched_readings[].old_status/old_confidence`, `meta.correction_log`. Doing it
   *inside* the frozen contract means keeping the history in `meta`, not adding a field to
   `FieldReading`. Gated on 1–3 being merged.
2. **UI: propagation panel** — `diff.summary` + `diff.obligations[].changes` (feat/ui).
3. Reset button in the UI wired to `POST /api/case/{id}/reset` for M5's repeated runs.
4. Nothing else. SQLite, multi-tenant and auth stay non-goals (IDEA_SCOPE §12/§13).
