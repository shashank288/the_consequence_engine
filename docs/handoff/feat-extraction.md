# Handoff — feat/extraction (M0 + M1)

## 1. M0 is VERIFIED — one real photographed page went through the live API

`fixtures/private/register_page.png` (1067×1373) → the full doc-digitization job
flow → structured output, **9.4 s wall clock**, job
`20260726_46a20ccd-4a7d-4e5b-abcb-cc6571da48b2`. Repeat it any time:

```bash
py -3.12 -c "from src.sarvam_client import doc_intelligence_extract as f; import json; print(json.dumps(f('fixtures/private/register_page.png'), indent=2)[:3000])"
```

`POST /api/case` runs it live end to end: photo in → plan out, with the two
unreadable cells refused and their evidence intact.

**Every worktree needs its own `.env`** — `config.py` loads it from the worktree
root, so a key in `Sarvam/.env` is invisible here. Copy it across.

## 2. ⚠️ Five documented facts that are WRONG — main should fix config.py + §5

`config.py` is main's file, so this branch did not touch it. All corrected
constants live in `src/sarvam_client.py`; nothing is blocked on the copy-across.

**a. The endpoint family is wrong.** It is `doc-digitization`, not
`document-intelligence`; `/api/document-intelligence/*` does not exist.

| `config.DOC_INTEL` (stale) | Actual, verified by call |
|---|---|
| `POST /api/document-intelligence/initialize` | `POST /doc-digitization/job/v1` |
| `POST /api/document-intelligence/get-upload-links` | `POST /doc-digitization/job/v1/upload-files` |
| `POST /api/document-intelligence/start` | `POST /doc-digitization/job/v1/{job_id}/start` |
| `GET /api/document-intelligence/status` | `GET /doc-digitization/job/v1/{job_id}/status` |
| `POST /api/document-intelligence/get-download-links` | `POST /doc-digitization/job/v1/{job_id}/download-files` |

**b. `output_format: "json"` does not exist.** The docs list it; the API 400s:
`body.job_parameters.output_format : Input should be 'html' or 'md'`. We send `md`.

**c. `job_parameters` is REQUIRED.** The docs say all fields are optional; an
empty body 400s with `body.job_parameters : Field required`.

**d. The result is a ZIP, not a document.** `download_urls` has one entry keyed
`document.zip`, content-type `application/octet-stream`, containing:

```
document.md              tables come back as HTML <table> inside the markdown
metadata/page_001.json   {"page_num", "image_width", "image_height", "blocks": [
                           {"block_id", "coordinates": {x1,y1,x2,y2},   <- PIXELS
                            "layout_tag", "confidence", "reading_order", "text"}]}
```

**e. `sarvam-105b` is a reasoning model with a 4096-token hard cap.** It bills
thinking against the answer budget. At the default 2048 the call returns **200
with `content: null`** and `finish_reason: "length"` after ~6.4k characters of
`reasoning_content` — a silent failure that looks like an empty answer. Our
normalisation prompt needs ~2.9k completion tokens. And the ceiling is fixed:
`max_tokens (5000) exceeds the maximum allowed for sarvam-105b for your
subscription tier (starter): 4096`. So headroom is ~1.2k tokens; a longer page
can still exhaust it, which is why a failed normalisation degrades the draft
instead of failing the run.

Also confirmed: `x-ms-blob-type: BlockBlob` is needed on the presigned PUT
(`storage_container_type: "Azure_V1"`); input must be **.pdf or .zip**, exactly
one file — a bare PNG is rejected, so photos are zipped with no re-encoding;
`job_id` is `YYYYMMDD_<uuid>`, not a bare UUID; the create response carries
undocumented `prompt_type`, `prompt`, `source`; there is **no synchronous vision
endpoint**; chat `response_format` supports `text | json_object | json_schema`
and the message carries `reasoning_content`, `refusal`, `tool_calls`.

## 3. Per-region confidence exists — and using it naively would break the demo

**Sarvam scores LAYOUT BLOCKS, not fields.** Our register page came back as two
blocks: a headline at **0.583** and the *entire table* at **0.912**. Handing that
0.912 to a cell read out of the table would have marked the stamp-occluded area
column as confidently read — the exact failure this product exists to prevent.

So a block confidence is used as a **ceiling**, never a verdict, unless the block
*is* the field. Within the block, `confidence.py` earns the number from evidence:
shape, verbatim presence, corroboration, OCR noise, and — the strongest signal on
this page — whether the cell holds multiple values.

## 4. What the real OCR actually did to the card-87 page

Sarvam marks a multi-line cell with `<br/>`, so the register page's deliberate
difficulties came back **explicitly flagged**, which is better than expected:

| Field | Extracted (rendered) | Conf | Outcome |
|---|---|---:|---|
| `survey_no` | `SN-143` | 0.85 | read |
| `khata_no` | `१३` | 0.85 | read |
| `father_name` | `रामय्या` | 0.85 | read |
| `owner_name` | `सुशीला बाई ; सुशीला देवी` | **0.05** | **refused** — cell holds 2 entries |
| `plot_area` | `१ एकड़ ०५ गुंठा ; तहसील ; ३ एकड़ ०४ गुंठा` | **0.05** | **refused** — cell holds 3 entries |

The struck-through correction returned **both names**, and the tehsil stamp bled
the word `तहसील` *into* the area cell along with two different areas. Row 3's
area came back empty — the stamp ate it entirely. Elsewhere the OCR made real
errors we did not plant: `रामय्या स.` → `रामऱ्या स.`, `लक्ष्मम्मा` → `लक्ष्मीम्मा`.

Neither refusal is a threshold artefact: the page genuinely says two things, and
DATASET.md's "the system must not silently pick one" is satisfied in the
strongest way — we pick neither, and both candidates survive in the refusal's
`SourceRef.quote` for a human to adjudicate.

Live plan output:

> **Get a legible reading of area (क्षेत्रफल), owner name (मालिक का नाम) for
> SN-143 on the record of rights — it could not be read from this photograph**

## 5. Three gates the LLM had to be put behind (all found by running it)

The model is a proposer; it never decides. Every one of these fired for real:

1. **A quote must be findable on the page.** Standard.
2. **A quote being on the page does not make it a requirement.** Asked for
   requirements, the model pointed at a *table row* — real text, so the quote
   gate passed it, and a fabricated dependency reached the plan. A requirement
   must now also be *stated* in requirement words (`_states_a_requirement`).
3. **On a table page the model may not contribute identity fields at all.** It
   returned every row's owner — four names for one field, which the sequencer
   would rightly read as a blocking mismatch between readings that were never in
   conflict. One register page holds several different plots.

Also: the model cannot set its own confidence, and cannot supply a date or
amount the page does not carry.

## 6. What feat/register and feat/ui can rely on

- **`SourceRef.bbox` is LAYOUT-BLOCK level, normalised 0–1** — for the refused
  cells it is the whole-table box, not the cell. `blocks[].bbox_px` carries the
  same box in pixels (PIL-ready) alongside `image_width`/`image_height`.
  **feat/register will need to subdivide it by row/column to crop one cell** —
  the row is identifiable from the quote text.
- Refused readings always keep `SourceRef.quote` with the page's own words, so
  the escalation view has something to show even without a crop.
- Original uploaded pixels are kept at `fixtures/raw/uploads/<case_id>/<file>`,
  deliberately not tempfile'd away, so crops can be made after the response.
- `raw_excerpt` carries provenance (`sarvam-doc-digitization` vs
  `offline-sample:…`), classification evidence, the row-selection reason, and
  every refusal reason with its confidence. Safe to surface in the UI.

## 7. Offline mode and the demo fallback

`SARVAM_OFFLINE=1` replays instead of calling out. It prefers a real cached
response (`fixtures/raw/<stem>.docintel.json`, written by every live call) and
otherwise falls back to `src/extraction/offline_sample.json`.

**That sample now contains the REAL captured response for `register_page`** —
verbatim, OCR errors and all — so the committed tests exercise genuine API
output on a fresh clone with no key. `counter_slip`, `bank_letter` and `default`
remain hand-authored stand-ins; the file's `_README` labels each one and a test
enforces that labelling.

With no key and no `SARVAM_OFFLINE`, `POST /api/case` returns **503 with the
reason** rather than quietly serving canned data. The operator's fallback stays
the explicit `POST /api/case/fixture/demo`, untouched and green.

Demo-day note: offline replay is a legitimate fallback **only if described as
one**. Every draft says `offline-sample:…` in `raw_excerpt`; the honest line is
"this is a recorded response, not a live call".

## 8. Files this branch owns and changed

| File | What |
|---|---|
| `src/sarvam_client.py` | job flow + ZIP unpacking, offline replay, raw caching, `chat`/`chat_json` |
| `src/extraction/pipeline.py` | drafts, HTML-table rendering, quote gates, doc typing, row selection |
| `src/extraction/confidence.py` | the earned-confidence model, block ceiling, multi-value penalty |
| `src/extraction/prompts.py` | normalisation prompt + requirement-key vocabulary |
| `src/extraction/offline_sample.json` | real capture (register_page) + labelled stand-ins |
| `tests/test_extraction.py` | 15 tests, no key needed |
| `src/app.py::create_from_uploads` | the sanctioned one-function exception |
