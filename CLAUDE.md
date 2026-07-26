# The Consequence Engine — agent instructions

**SCOPE GATE: read `IDEA_SCOPE.md` before any change.** It is the control plane.
If a change does not advance the ACTIVE milestone's acceptance test, it goes to
the parking lot (§13). Idea selection is OVER — do not re-litigate it.

## What this is
Sarvam Buildathon build (submission 16:30 IST 2026-07-26). Photograph a stack of
Indian land-mutation papers → ONE ordered plan with quoted blocking evidence,
refusals instead of guesses. Scored Sarvam parameter: **Document Intelligence**.

## Run
**Use `py -3.12` on this machine — bare `python` resolves to 3.8, which breaks pydantic v2 typing.**
```bash
py -3.12 -m pip install -r requirements.txt
py -3.12 -m pytest -q                        # must stay green — no key needed
py -3.12 -m uvicorn src.app:app --port 8000  # http://localhost:8000 → "Load demo case"
py -3.12 -m scripts.run_case                 # CLI golden path
```
Secrets: copy `.env.example` → `.env`, set SARVAM_API_KEY. Never commit it.

## Branch ownership (STRICT — parallel agents depend on this)
| Branch | Owns ONLY | Acceptance test |
|---|---|---|
| main | contracts.py, config.py, IDEA_SCOPE.md, fixtures/, tests/, merges | pytest green |
| feat/extraction | src/sarvam_client.py, src/extraction/ | real photo → draft with read-or-refused deadline; raw responses cached to fixtures/raw/ |
| feat/sequencer | src/sequencer/ | tests/test_sequencer.py |
| feat/register | src/register/, web/crops/ | held-out handwritten page → ≥1 refusal WITH crop + 1 contradiction vs mocked prior record |
| feat/case-memory | src/case_store/ | correction propagates + reload resumes (keep load_case/save_case signatures) |
| feat/ui | web/ | judge flow clickable; edges panel is the hero |
| feat/voice | src/voice/ | plan plays in Hindi. FIRST CUT if behind |

Rules:
1. **Touch only your branch's files.** `src/contracts.py` is FROZEN — changes need a
   main PR titled `CONTRACT-CHANGE:` + a row in IDEA_SCOPE.md §16.
2. Rebase on main before PR. Merge order: extraction → sequencer → register →
   case-memory → ui → voice.
3. `python -m pytest -q` green before every merge. The fixture golden path
   (`POST /api/case/fixture/demo`) must NEVER break — it is the demo fallback.
4. Refusal policy is the product: a consequence-bearing field below
   `REFUSE_BELOW` (config.py) is refused and routed — NEVER guessed, NEVER
   silently dropped.
5. Never assert legal rules, scheme deadlines, or procedures not quoted from a
   supplied page. Non-goals in IDEA_SCOPE.md §12 are binding.
6. Verified Sarvam facts live in config.py + IDEA_SCOPE.md §5. Anything marked
   VERIFY gets verified with ONE real call before being depended on.
