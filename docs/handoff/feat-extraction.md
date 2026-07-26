# HANDOFF — feat/extraction (M0 · M1 · Document Intelligence)

| Field | Value |
|---|---|
| Branch | `feat/extraction` |
| Commit | `4a5ae16` (2026-07-26 15:21 IST), rebased on `main` |
| Status | **Verified** — M0 ran against the LIVE Sarvam API; `.\scripts\verify.ps1` green (48 passed · golden path ok · contract untouched) |
| Merge position | **first** (extraction → sequencer → register → case-memory → ui → voice) |
| Rubric | Document Intelligence ×2.5 → real handwritten-style page → structure + source refs + controlled uncertainty |
| Needs a Sarvam key? | **No** for tests, the fixture path, or the offline demo. **Yes** for a live photo. |

Read with: `docs/agents/feat-extraction.md` (the brief), `IDEA_SCOPE.md` §5 (sponsor
matrix — **needs the corrections in §5 below**), §8 M0/M1, `docs/DATASET.md`.

---

## 1. What shipped

Brief tasks 1 and 2 complete, acceptance test written, app wired.

| # | Task | Where |
|---|---|---|
| 1 | M0 — `doc_intelligence_extract` against the real job API, shapes recorded, raw cached | `src/sarvam_client.py` |
| 2 | M1 — `extract_drafts`: page → `ObligationDraft` with quotes, confidences, refusals | `src/extraction/pipeline.py` |
| 3 | Acceptance + policy tests, no key needed | `tests/test_extraction.py` |
| 4 | `POST /api/case` real pipeline (was `501`) | `src/app.py::create_from_uploads` |

**Files touched (nothing outside the brief's ownership):**

```
src/sarvam_client.py               job flow + ZIP unpack, offline replay, chat/chat_json
src/extraction/__init__.py         public surface + status
src/extraction/pipeline.py    NEW  drafts, HTML tables, quote gates, doc typing, rows
src/extraction/confidence.py  NEW  the earned-confidence model
src/extraction/prompts.py     NEW  normalisation prompt + requirement-key vocabulary
src/extraction/offline_sample.json NEW  real capture + labelled stand-ins
tests/test_extraction.py      NEW  14 tests
src/app.py                         create_from_uploads only (the sanctioned exception)
```

`src/contracts.py` untouched — everything fits inside the FROZEN contract.

**M0, verified live:** `fixtures/private/register_page.png` (1067×1373) →
doc-digitization job `20260726_46a20ccd-4a7d-4e5b-abcb-cc6571da48b2` → structured
output, **9.4 s** wall clock.

```bash
py -3.12 -c "from src.sarvam_client import doc_intelligence_extract as f; import json; print(json.dumps(f('fixtures/private/register_page.png'), indent=2)[:3000])"
```

---

## 2. Public surface

```python
from src.extraction.pipeline import extract_drafts, presence_facts, label

extract_drafts(image_paths: list[str]) -> list[ObligationDraft]
    # one draft per document, ids O1..On in input order.
    # Raises SarvamUnavailable when there is neither a key nor SARVAM_OFFLINE=1.
presence_facts(drafts) -> list[str]
    # requirement keys satisfied by a document's PRESENCE (death certificate,
    # identity document) — feed to Case.provided_facts / done_keys.
label(field_name) -> str            # "plot_area" -> "area (क्षेत्रफल)", for UI

from src.sarvam_client import (doc_intelligence_extract, chat, chat_json,
                               translate, tts, offline_mode, SarvamUnavailable,
                               DOC_DIGITIZATION, CHAT_MAX_TOKENS)

doc_intelligence_extract(path, *, language="hi-IN", output_format="md",
                         poll_timeout_s=240) -> dict
chat(messages, **kw) -> str         # max_tokens defaults to 4096; raises
                                    # ValueError on null content (see §5e)
chat_json(messages, **kw) -> dict   # response_format json_object, fences tolerated

from src.extraction.confidence import score, Score, MULTIVALUE
score(field, value, page_text="", api_confidence=None, ceiling=None) -> Score
    # Score(value, reasons, penalties); .decisive is the refusal reason to show
```

`doc_intelligence_extract` returns:

```python
{"provenance": "sarvam-doc-digitization" | "offline-replay:<path>" | "offline-sample:<key>",
 "offline": bool, "source_path": str, "job_id": str | None,
 "requested": {"language", "output_format"},
 "documents": [{"file_name": "document.zip",
                "content": {"markdown": str,
                            "pages": [{"page_number", "text", "image_width",
                                       "image_height",
                                       "blocks": [{"text", "confidence", "bbox",
                                                   "bbox_px", "layout_tag",
                                                   "block_id", "reading_order"}]}]}}],
 "api_trace": {step: response_json}}        # the M0 shape record
```

**The requirement-key vocabulary is the joint between documents** — the sequencer
matches `needs` → `provides` by exact string, so a free-text key silently never
matches and the plan under-blocks. Extend it in `prompts.REQUIREMENT_KEYS`:

`death_certificate` · `heirship_certificate` · `record_name_matches_id` ·
`record_owner_resolved` · `mutation_completed` · `identity_proof` ·
`application_fee_paid` · `prior_order`

`pipeline.DOC_TYPE_PROVIDES` is an **authored** map (doc type → keys it satisfies
once done), not an extracted claim: `mutation_register_page` →
`[record_owner_resolved, record_name_matches_id]`, `counter_slip` →
`[mutation_completed]`, `bank_letter` → `[bank_succession_done]`. Edges still come
only from the other pages' own words.

---

## 3. HTTP API

| Method | Path | Notes |
|---|---|---|
| POST | `/api/case` | **now real** — uploads → Doc-Intelligence → drafts → plan → saved |
| POST | `/api/case/fixture/{name}` | unchanged, still the demo fallback |

`POST /api/case` (multipart, field name `files`, one or more):

- **200** → full case dump with `plan`, exactly as the fixture endpoint returns.
- **422** → no files.
- **503** → `SARVAM_API_KEY is not set, so <file> cannot be read…`. It does **not**
  fall back to fixture data: a demo that shows canned readings while implying they
  came off the wire is the one failure this product cannot survive.

Uploads are kept at `fixtures/raw/uploads/<case_id>/<filename>` (git-ignored),
deliberately not tempfile'd away, so `feat/register` can crop after the response.
`provided_facts` and `done_keys` are seeded from `presence_facts(drafts)`.

---

## 4. The refusal model (why the number is trustworthy)

**Sarvam scores LAYOUT BLOCKS, not fields.** Our register page came back as two
blocks: headline **0.583**, and the *entire table* at **0.912**. Handing 0.912 to a
cell read out of the table would have marked the stamp-occluded area column as
confidently read — precisely the failure this product exists to prevent.

So a block score is a **ceiling**, never a verdict, unless the block *is* the
field. Within it, `confidence.py` earns the number from inspectable evidence:

```
base 0.35   we read something, nothing more is known
+0.35  the value has the SHAPE this field takes (a date parses; an area is
       "<n> एकड़ <n> गुंठा"; a survey no is "SN-142/2"; a name is 1-3 tokens)
+0.15  it appears verbatim in the page text        +0.05  page repeats it
-0.35  the cell holds MULTIPLE values (a correction/overwrite)
-0.10  the field has a known shape and this misses it
-0.25  OCR-noise characters                        -0.05  ambiguous date order
ceiling 0.95 — we never saw the paper; certainty is not on offer
```

Tuned against `REFUSE_BELOW = 0.75`. **Live output on the card-87 page:**

| Field | Extracted (rendered) | Conf | Outcome |
|---|---|---:|---|
| `survey_no` | `SN-143` | 0.85 | read |
| `khata_no` | `१३` | 0.85 | read |
| `father_name` | `रामय्या` | 0.85 | read |
| `owner_name` | `सुशीला बाई ; सुशीला देवी` | **0.05** | **refused** — 2 entries |
| `plot_area` | `१ एकड़ ०५ गुंठा ; तहसील ; ३ एकड़ ०४ गुंठा` | **0.05** | **refused** — 3 entries |

> **NEXT SINGLE ACTION:** Get a legible reading of area (क्षेत्रफल), owner name
> (मालिक का नाम) for SN-143 on the record of rights — it could not be read from
> this photograph

Sarvam marks a multi-line cell with `<br/>`, so the page's planted difficulties
came back **explicitly flagged**: the struck-through correction returned *both*
names, and the tehsil stamp bled `तहसील` *into* the area cell alongside two
different areas. Row 3's area came back empty — the stamp ate it. It also made
errors we did not plant (`रामय्या स.`→`रामऱ्या स.`, `लक्ष्मम्मा`→`लक्ष्मीम्मा`).

Neither refusal is a threshold artefact: the page genuinely says two things.
DATASET.md's *"the system must not silently pick one"* is satisfied in the
strongest form — we pick neither, and both candidates survive in the refusal's
`SourceRef.quote` for a human to adjudicate.

**Three gates the LLM sits behind.** It proposes; it never decides. All three
were added after watching it fail on real output:

1. A quote must be findable verbatim on the page.
2. **A quote being on the page does not make it a requirement** — asked for
   requirements, it pointed at a *table row*, which passed gate 1 and put a
   fabricated dependency in the plan. It must now also be stated in requirement
   words (`_states_a_requirement`).
3. **On a table page it contributes no identity fields at all** — it returned all
   four rows' owners, four names for one field, which the sequencer would rightly
   read as a blocking mismatch between readings never in conflict. One register
   page holds several different plots.

It also cannot set its own confidence, and cannot supply a date or amount the page
does not carry. A failed normalisation **degrades** the draft (deterministic reader
only, said so in `raw_excerpt`); it never fails the run.

---

## 5. ⚠️ VERIFIED Sarvam facts — main should fix `config.py` + IDEA_SCOPE §5

Everything here was found by calling the API. `config.py` is main's file, so this
branch did not touch it; corrected constants live in `sarvam_client`. **Nothing is
blocked on the copy-across** — no code imports `DOC_INTEL` any more.

**a. The endpoint family is wrong** — `doc-digitization`, not
`document-intelligence`. `/api/document-intelligence/*` does not exist.

| `config.DOC_INTEL` (stale) | Actual |
|---|---|
| `…/initialize` | `POST /doc-digitization/job/v1` |
| `…/get-upload-links` | `POST /doc-digitization/job/v1/upload-files` |
| `…/start` | `POST /doc-digitization/job/v1/{job_id}/start` |
| `…/status` | `GET /doc-digitization/job/v1/{job_id}/status` |
| `…/get-download-links` | `POST /doc-digitization/job/v1/{job_id}/download-files` |

**b. `output_format: "json"` does not exist.** The docs list it; the API 400s —
`body.job_parameters.output_format : Input should be 'html' or 'md'`. We send `md`.

**c. `job_parameters` is REQUIRED.** Docs say optional; `{}` 400s with
`body.job_parameters : Field required`.

**d. The download is a ZIP, not a document.** One `download_urls` entry keyed
`document.zip`, `application/octet-stream`, containing:

```
document.md              tables come back as HTML <table> inside the markdown
metadata/page_001.json   {"page_num","image_width","image_height","blocks":[
                           {"block_id","coordinates":{x1,y1,x2,y2},  <- PIXELS
                            "layout_tag","confidence","reading_order","text"}]}
```

**e. `sarvam-105b` is a reasoning model with a hard 4096 cap.** It bills thinking
against the answer budget. At the default 2048 the call returns **200 with
`content: null`** and `finish_reason: "length"` after ~6.4k chars of
`reasoning_content` — a silent failure that reads like an empty answer. Our
prompt needs ~2.9k completion tokens. The ceiling is fixed: `max_tokens (5000)
exceeds the maximum allowed for sarvam-105b for your subscription tier (starter):
4096`. Headroom over a page-sized prompt is ~1.2k tokens.

**Also confirmed:** input must be **.pdf or .zip**, exactly one file, ≤200 MB,
≤10 pages — a bare PNG is rejected, so photos are zipped with no re-encoding;
`x-ms-blob-type: BlockBlob` **is** required on the presigned PUT
(`storage_container_type: "Azure_V1"`); `job_id` is `YYYYMMDD_<uuid>`; the create
response carries undocumented `prompt_type`, `prompt`, `source`; there is **no
synchronous vision endpoint** — the async job is the only route; chat
`response_format` supports `text | json_object | json_schema`, and the message
carries `reasoning_content`, `refusal`, `tool_calls`.

---

## 6. Tests · verification

```bash
py -3.12 -m pytest -q      # 48 passed (14 extraction + 12 memory + 22 sequencer)
.\scripts\verify.ps1       # tests + fixture golden path + frozen-contract check
```

`tests/test_extraction.py` (14) covers: the acceptance draft (no field is ever a
bare value), the stamp-occluded refusal with evidence intact, the overwritten
owner refused rather than picked, requirements always verbatim-quoted, the
deadline read with its printed form as evidence, a date the page does not frame as
a deadline never promoted, unreadable input → unknown bucket, model proposals
without a page quote dropped, confidence never 1.0, no-key-no-offline refusing,
per-entry provenance labelling of the sample, photos→plan with a quoted blocking
edge, presence facts, and **the live job flow driven step-by-step against the
verified shapes** (endpoint order, zip wrapping, Azure header, ZIP unpack, bbox
normalisation).

Two autouse guards keep it hermetic: `SARVAM_OFFLINE=1`, and `RAW_DIR` redirected
to `tmp_path` so a real cached response cannot silently change what is asserted.

**Offline replay** prefers a real cached response
(`fixtures/raw/<stem>.docintel.json`, written by every live call) and otherwise
falls back to `src/extraction/offline_sample.json`. That file now holds the **REAL
captured response for `register_page`** — verbatim, OCR errors and all — so the
committed tests exercise genuine API output on a fresh clone with no key.
`counter_slip`, `bank_letter` and `default` remain hand-authored stand-ins; the
`_README` labels each one and a test enforces the labelling.

---

## 7. Secrets

- `.env` is **per worktree** — `config.py` loads it from the worktree root, so a
  key in `Sarvam/.env` is invisible in `ce-worktrees/extraction`. Copy it across
  before any live run. This cost us the first M0 attempt.
- `.env.example` stays empty; no key in any tracked file. `fixtures/raw/`,
  `fixtures/private/` and `cases.json` are git-ignored, so no cached response,
  photograph or case file is committed.
- ⚠️ Still true from the case-memory handoff: **the key is in git history**
  (`dddebe2`, `f3eb0b6`, both on `origin`). **Rotate after the event.**
- `config.py` now calls `load_dotenv()` (landed on main), so `pytest`,
  `scripts.run_case` and bare `uvicorn` all see `.env`.

---

## 8. Merging this branch

1. Already rebased on `main` (`4a5ae16`). Merge order: **extraction first.**
2. `.\scripts\verify.ps1` must be green.
3. Expected conflicts: **`src/app.py` only** — the import block and
   `create_from_uploads`. Resolution rule: keep this branch's `create_from_uploads`
   and its three new imports (`extract_drafts`, `presence_facts`,
   `SarvamUnavailable`); keep the other branch's everything else.
4. `src/extraction/*` and `tests/test_extraction.py` are new — no conflicts.
5. After merging, apply §5a–e to `config.py` and IDEA_SCOPE §5.

---

## 9. Open dependencies (NOT this branch's work)

| Item | Owner | Effect |
|---|---|---|
| **Cell-level crops** | `feat/register` | `SourceRef.bbox` is **layout-block level**, normalised 0–1 — for the refused cells it is the whole-table box, not the cell. `blocks[].bbox_px` has the same box in pixels with `image_width`/`image_height`. Register must subdivide by row/column; the row is identifiable from the quote text. Originals are at `fixtures/raw/uploads/<case_id>/`. |
| **Real photos of the other doc types** | Shashank | Only the register page has been through the live API. `counter_slip`, `bank_letter` and the unknown slip run against hand-authored stand-ins, so **M2's "all 4–5 doc types on real docs" is not proven**. The code path is identical — it needs images, not code. |
| `config.py` + IDEA_SCOPE §5 corrections | main | §5. Cosmetic; nothing imports the stale constants. |
| Rendering `raw_excerpt` refusal reasons | `feat/ui` | Optional. It carries provenance, classification evidence, row-selection reason and every refusal reason with its confidence — safe to surface verbatim. |

---

## 10. Follow-ups (priority order, ~65 min to submission at time of writing)

1. **Photograph a counter slip and a bank letter** and run them live. Highest
   value per minute left: it converts the multi-document chain from stand-in to
   real and is the difference between M1 and M2 on real inputs. No code needed.
2. **Cell-level bbox** so the escalation crop shows the cell, not the table
   (feat/register). The table block box plus the row index from the quote is
   enough to subdivide.
3. Run the **held-out page** (`register_holdout.png`, seed 13) once, live, and
   record the field accuracy / refusal counts — that is the Impact L4 number
   IDEA_SCOPE §6 asks for. Deliberately not opened during this build.
4. Nothing else. Multi-page documents, fine-tuning and real government lookups
   stay non-goals (IDEA_SCOPE §12/§13).
