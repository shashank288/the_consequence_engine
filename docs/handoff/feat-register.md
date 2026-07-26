# HANDOFF — feat/register (M3 · card 87 · Document Intelligence + Delight)

| Field | Value |
|---|---|
| Branch | `feat/register` |
| Handoff written | 2026-07-26 16:05 IST |
| Status | **Verified** — acceptance test passes on the held-out page; `.\scripts\verify.ps1` green (53 passed · golden path ok · contract untouched) |
| Merge position | after `feat/sequencer`, before `feat/case-memory` |
| Rubric | Document Intelligence ×2.5 → **L4–L5**; Delight ×1 → **L4** |
| Needs a Sarvam key? | **No.** Every test, the CLI and the crops are local work on an image. |

Read with: `docs/agents/feat-register.md` (the brief), `docs/DATASET.md` (what we may
claim about the page), `IDEA_SCOPE.md` §8 M3.

---

## 1. What shipped

All three brief tasks, plus the page reader they needed.

| # | Task | Where |
|---|---|---|
| 1 | Crop generation → `SourceRef.crop_path`, servable at `/crops/<id>.png` | `src/register/crops.py` |
| 2 | Handwriting-aware refusal policy (threshold **and** page evidence) | `src/register/policy.py` |
| 3 | Contradiction vs the mocked prior record | `src/register/contradictions.py`, `records.py` |
| — | Page reader: form registration + seal/strike detection (no OCR) | `src/register/reader.py` |
| — | Entry point + CLI demo | `src/register/__init__.py`, `__main__.py` |

```
src/register/__init__.py        build_plan_with_register(), re-exports
src/register/reader.py     NEW  register the form on the photo, find obstructions
src/register/crops.py      NEW  bbox -> cropped cell PNG under web/crops/
src/register/policy.py     NEW  refusal policy for mutation_register_page
src/register/contradictions.py  NEW  page vs records system
src/register/records.py    NEW  mocked prior records (moved out of __init__)
src/register/__main__.py   NEW  py -3.12 -m src.register <page>
tests/test_register.py     NEW  19 tests
src/app.py                      2 lines (the brief's allowance) — see §6
```

`src/contracts.py` untouched. `web/index.html` untouched (feat/ui owns it — see §5).
`config.py` untouched: `REFUSE_BELOW` is layered on, never changed.

---

## 2. Public surface (import from `src.register`)

```python
build_plan_with_register(case, pages=None) -> Plan   # policy -> build_plan -> contradictions
apply_register_policy(drafts, pages=None, audits=None) -> drafts   # brief's signature
check_contradictions(drafts) -> list[Mismatch]
crop_field(image_path, bbox, out_dir="web/crops", name=None) -> str  # "crops/<id>.png"
audit_page(image_path) -> PageAudit                  # registration + obstructions
prior_record(plot_no) -> dict | None                 # unchanged signature
REGISTER_REFUSE_BELOW = 0.85 ·  REGISTER_DOC_TYPES ·  CropUnavailable
```

`pages` maps `doc_id -> image path`. Omit it and images are looked up as
`fixtures/private/<doc_id>.<png|jpg|jpeg|webp>`, which is why the CLI works with a
bare filename. Everything mutates `case.drafts` in place and is **idempotent** — safe
on a reloaded case, safe to call twice.

---

## 3. The refusal policy — two tiers, both stated

**Tier 1 · page evidence beats confidence.** `reader.py` registers the ruled form onto
the photograph, finds seal ink and correction strokes by colour, and measures how much
of each cell's *writing band* they cover. A reading whose bbox sits under an obstruction
is refused **regardless of its confidence**. On the demo pages this refuses an area cell
read at **0.91** — above every threshold in the system — because the tehsil seal is on
top of it. That is the L4→L5 move: confidence cannot catch a confidently-wrong reading,
pixels can.

**Tier 2 · a stricter threshold, gated on having looked at the page.**
`REGISTER_REFUSE_BELOW = 0.85` (vs the global `REFUSE_BELOW = 0.75`) applies to
consequence-bearing fields (`owner_name`, `plot_no`, `survey_no`, `area`, `plot_area`,
`date`, `deadline`) on a register page **whose image we hold**. The stricter bar is a
claim about the page — "this is degraded handwriting, 0.80 here is not 0.80 on a printed
slip" — so we require having actually measured the page before making it. Two
consequences, both intended:

* Supply the image → the strict bar. No image → the global bar, unchanged.
* This branch therefore **cannot silently re-refuse readings in the packaged fixture
  demo** that feat/case-memory's and feat/ui's beats depend on. `owner_name` @ 0.81 in
  `fixtures/case_demo.json` stays `read`, the cosmetic mismatch still fires, and
  `test_fixture_demo_plan_is_unchanged_by_this_branch` locks that in.

**Tier 2b · an extractor's own hint** ("seal", "overwritten", "faded", "multiple hands"
in `source.quote`) forces a refusal with no image at all. That is how the fixture's
`plot_area` now says *why* it was refused.

Every refusal writes its reason into `source.quote`, idempotently:

```
१ एकड़ ०५ गुंठा — REFUSED (occluded_by_seal): an office seal is stamped across this
cell — measured over 57% of the writing; refused despite a read confidence of 0.91,
because the page itself does not support it
```

Reason keys: `occluded_by_seal`, `overwritten`, `low_confidence`, `multiple_hands`,
`illegible`.

**A refused field never travels with a value.** The plan's copy is emptied
(`_strip_refused_values`); the *draft* keeps the superseded reading so
feat/case-memory's correction flow still reports it as `Correction.old`. That is
deliberate — it is the same split the sequencer already uses.

### Known bias, stated rather than hidden

The obstruction test errs toward refusing. On the demo page it refuses **3 of 4** area
cells; the third (`SN-145`) has the seal's arc grazing the line above the text, which a
human would call legible. The measured coverage is printed in the reason (14% vs 57%),
so a marginal call is visibly marginal, and the crop settles it in one glance. A wrong
refusal costs a look; a wrong reading costs a rejected mutation. Tightening this is the
first parking-lot item (§9) — I did not tune it further because tuning to two visible
seeds is how you overfit to a synthetic page.

---

## 4. What the page reader actually does (and does not)

* **Registers the form**: finds the sheet's four extreme paper pixels, labels them by
  matching the edge-length ratio to the form's aspect, and maps form coordinates
  (`scripts/make_register_page.py` draws at 1700×2200) onto the photograph. Falls back to
  a flat-on assumption and sets `registered=False` rather than cropping the wrong cell.
* **Finds obstructions**: classifies every pixel of a 640-wide scan as seal / strike /
  ink by colour, accumulates 8-px tiles, and groups tiles into blobs with a 2-tile gap
  tolerance (a rubber stamp is a *ring* — strict adjacency reports one seal as eight
  smudges). Tiling is what makes it survive sensor noise.
* **Locates the writing**: the ink mask gives each cell's writing band, so "the seal is
  near this cell" and "the seal is on these words" are different questions.
* **Reads no text and invents no value.** Transcription is feat/extraction's job. This is
  a second, independent opinion on whether the paper was legible at all.

Runs in ~0.3 s per page, Pillow only, imported lazily so a case with no image never
depends on an imaging library.

---

## 5. For feat/ui — the crop is the Delight moment

`crop_field` writes to `web/crops/` (git-ignored) and returns a **web path**, so the
existing `StaticFiles` mount serves it with no new route. Verified: `GET
/crops/<id>.png` → `200 image/png`.

`web/index.html` currently renders refusals **without** the image. One line in the
refusals template turns it into the demo beat:

```js
${r.source && r.source.crop_path
  ? `<br><img src="${r.source.crop_path}" alt="refused field"
       style="max-width:100%;margin-top:6px;border:1px solid #5c2d3d;border-radius:6px">`
  : ''}
```

The escalation panel must show **the cropped cell, not the whole page** — a judge should
be able to look at it and agree "yes, that genuinely is unreadable". Filenames are
deterministic (`<page>-<field>-<hash8>.png`), so repeated demo runs overwrite rather than
accumulate.

Mismatch rendering already works unchanged; contradictions arrive in `plan.mismatches`
with the same shape. A contradiction is recognisable by a reading whose
`source.doc_id` starts with `prior_record:`.

---

## 6. Wiring — the two lines in `src/app.py`, and what is NOT wired

```python
from .register import build_plan_with_register          # + import
...
case.plan = build_plan_with_register(case)              # was build_plan(case)
```

in `create_from_fixture` only. `feat/extraction` owns `create_from_uploads` and was
editing it — untouched.

**Not wired (deliberately, outside the allowance):** `mark_done` and
`case_store.apply_correction` still call plain `build_plan`. Refusals survive there
(status is stored on the draft), but **contradictions are recomputed only through
`build_plan_with_register`**, so they drop out of the plan after a status-lookup or a
correction. Fix is one word at each call site, for whoever owns them:

| File | Line | Change |
|---|---|---|
| `src/app.py` `mark_done` | `case.plan = build_plan(case)` | → `build_plan_with_register(case)` |
| `src/case_store/corrections.py` | both `build_plan(case)` calls | → `build_plan_with_register(case)` |

Safe to do: the function is idempotent and is a no-op for cases with no register page
image (§3), and the fixture-equivalence test guards it.

**To get the register page into the demo without extraction**, either:

```bash
py -3.12 -m src.register fixtures/private/register_page.png --out fixtures/case_register.json
# then: POST /api/case/fixture/register
```

(`fixtures/` is main's, so I did not commit the file), or call
`reader.draft_from_page(image, doc_id, rows)` from the extraction pipeline once it
returns values — it attaches this page's measured geometry to whatever text a model read.

---

## 7. Contradictions vs the records system

`records.py` holds four synthetic plots, deliberately mixed-script because a real records
database is. Comparison reuses `sequencer.text.cross_script_verdict` — it proves a match
or admits it cannot tell, and **a proven match raises nothing**, because a system that
flags `लक्ष्मम्मा` vs `Lakshmamma` teaches its user to ignore the panel.

| Plot | Page | Records system | Verdict |
|---|---|---|---|
| SN-142/2 | `रामय्या स.` | `Ramaiah S.` (1998) | **unknown** — skeletons `rmyy s` vs `rm s`; routed for a human |
| SN-143 | struck through | `Sushila Devi` (2004) | **blocking** — the page's entry was refused; which name is current cannot be settled from this page |
| SN-144/1 | `लक्ष्मम्मा` | `Lakshmamma` (1987) | proven same name → **no flag** |
| SN-145 | `गोविंद राव` | `गोविंद राव` (2011) | identical → **no flag** |

Owners are paired to plots **by row geometry** (shared horizontal band), never by
position in a list, so a page listing four plots cannot manufacture a cross-row
contradiction. Plot lookup is exact (whitespace/case fold only): a half-read plot number
matches nothing rather than the wrong record.

Readings from rows the obligation is not about are named `area@SN-144/1` — they still get
policy, refusals and crops (the seal covers three rows and a human should be told), but
they do not pretend to be this obligation's identity. Without that, the sequencer
correctly reads four `owner_name` readings on one obligation as one person named four
ways.

---

## 8. Tests · verification

```bash
py -3.12 -m pytest -q            # 53 passed (34 pre-existing + 19 here)
.\scripts\verify.ps1             # green: tests · golden path · contract untouched
py -3.12 -m src.register fixtures/private/register_holdout.png
```

Page images are git-ignored; the tests **generate them on demand** from
`scripts/make_register_page.py` and skip if that is impossible (no Devanagari font).

**Acceptance test — live, on the held-out page (seed 13, never opened during the build):**

```
page       fixtures\private\register_holdout.png  1087x1390   registered=True
obstruction seal   [0.675,0.176,0.875,0.323]   strike [0.312,0.186,0.450,0.225]
REFUSED (4, all with crops)
  owner_name@SN-143  0.79  overwritten        31% of the writing
  area@SN-143        0.91  occluded_by_seal   14%
  area@SN-144/1      0.91  occluded_by_seal   46%
  area@SN-145        0.88  occluded_by_seal   14%
CONTRADICTIONS  [unknown] SN-142/2 · [blocking] SN-143 vs 'Sushila Devi' (2004)
```

Same shape on both visible pages (seed 42 / seed 7): registered, 4 refusals with crops,
2 contradictions. **Honest caveat:** the generator varies *degradation* by seed, not
content — so the held-out page tests the reading difficulty (skew, lighting, seal angle,
folds) on unseen input, not unseen text. Say that if asked; do not claim more.

---

## 9. Known limits (say these plainly if a judge asks)

1. **Over-refusal at the margin** — §3. First follow-up.
2. **Registration assumes a flat-on photo.** Perspective is not modelled; a strongly
   angled shot sets `registered=False` and coordinates degrade to the flat-on assumption
   (crops drift, refusals still fire). No silent wrong crop.
3. **Colour thresholds are tuned to violet stamp ink and red correction ink**, measured
   on the two visible pages. A black-ink stamp would be missed by tier 1 — tier 2 and the
   extractor-hint route still cover it.
4. **This module reads no text**, so it cannot detect a *wrong* reading, only an
   unsupportable one.
5. The prior records are a **mock**. No real lookup, no real person's data
   (docs/DATASET.md).

## 10. Follow-ups, in priority order

1. Tighten the obstruction test (§3) — needs a third and fourth page, ideally the
   handwritten-and-photographed one from `docs/DATASET.md` §A, not more seeds.
2. Wire the two remaining `build_plan` call sites (§6) so contradictions survive a
   correction and a status lookup.
3. `feat/ui`: the one-line crop `<img>` (§5) — this is the Delight moment and it is
   currently invisible.
4. Generate `fixtures/case_register.json` (main owns `fixtures/`) for a second golden
   path that shows the register page end-to-end without extraction.
5. Nothing else. Deskewing, perspective correction and real OCR here stay non-goals.
