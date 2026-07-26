# AGENT BRIEF — feat/register  (M3 — the Document Intelligence score lives here)

Read `../../IDEA_SCOPE.md` §8 M3 and `../../CLAUDE.md` first.

## Mission
Handle **library card 87**: the decades-old handwritten regional-script
mutation-register page. This branch is what moves Document Intelligence (×2.5)
from L4 to L5 and supplies the Delight moment. It is the highest-value branch
after extraction.

## Files you own
- `src/register/` (extend `__init__.py`, add `crops.py`, `policy.py`)
- `web/crops/` (generated output — git-ignored)
- `tests/test_register.py` (new)

**Forbidden:** `src/contracts.py` (FROZEN), `src/sequencer/core.py`,
`src/extraction/`, `src/app.py` except the two lines noted below.

## Task 1 — crop generation (this IS the Delight moment)
`src/register/crops.py`:

```python
def crop_field(image_path: str, bbox: list[float], out_dir="web/crops") -> str
```

- `bbox` is `[x0,y0,x1,y1]` normalised 0–1 (see `SourceRef`). Convert to pixels
  with Pillow, pad ~8%, save PNG, return a **web-servable path** (`crops/<id>.png`).
- Write that path into `FieldReading.source.crop_path`.
- The escalation panel must show **the cropped cell, not the whole page.** A judge
  should be able to look at the crop and agree "yes, that genuinely is unreadable."

## Task 2 — handwriting-aware refusal policy
`src/register/policy.py`: handwritten pages need a **different, stated** threshold
from printed ones. Export `apply_register_policy(drafts) -> drafts` that:
- uses a documented threshold for `doc_type == "mutation_register_page"`
- refuses on `owner_name`, `plot_no`, `survey_no`, `area`, `date`
- records **why** it refused (low confidence / occluded by seal / overwritten /
  multiple hands) in the `FieldReading.source.quote` if the API gives a hint

Do not change the global `REFUSE_BELOW` in `config.py` — layer on top of it.

## Task 3 — contradiction vs the prior record
`prior_record(plot_no)` already exists as a mock. Build:

```python
def check_contradictions(drafts) -> list[Mismatch]
```

Compare the extracted owner against the mocked prior entry for the same plot and
emit a `Mismatch` with `classification` and a plain-language `reason`. This is
card 87's second demo beat: *"this page contradicts the last accepted entry."*

Wire it so the plan surfaces these — coordinate with main; the cleanest hook is
`Case.drafts` being policy-processed **before** `build_plan` is called (add the
call in `src/app.py` where the case is assembled, two lines, that's your allowance).

## Acceptance test
> A held-out handwritten page produces **≥1 refused field routed with its cropped
> image**, and **1 contradiction flagged** against the mocked prior record — live,
> on a page never used during the build.

## If behind (cut in this order)
1. Drop crop images → keep refusal with quote only (Delight drops but survives).
2. Drop contradiction check → keep refusal only.
Never drop the refusal itself. It is the product.

## Verify
```bash
py -3.12 -m pytest -q
py -3.12 -m uvicorn src.app:app --port 8000   # escalation panel shows a crop
```
Merge after `feat/extraction` and `feat/sequencer`.
