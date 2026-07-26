# Handoff — feat/extraction (M0 + M1)

## 1. The headline, honestly

**M0's live call did not happen: there is no `SARVAM_API_KEY` in `.env`** (the
key slot is present but empty, in this worktree and in the main one). So the
riskiest dependency in the project is still unproven against the real API.

What landed instead, per the brief's "if no API key yet" branch:

- the full job flow implemented against the **documented** request/response
  shapes, which were fetched from docs.sarvam.ai today and are recorded as
  comments in `src/sarvam_client.py`;
- a `SARVAM_OFFLINE=1` replay switch and a labelled stand-in response, so the
  whole pipeline is runnable, testable and demoable with no key at all;
- every raw response cached to `fixtures/raw/`, and the first live call writes
  `fixtures/raw/<stem>.docintel.json`, which replay then prefers over the
  stand-in. **The moment a key lands, one command upgrades the demo.**

Run it the second you have a key:

```bash
py -3.12 -c "from src.sarvam_client import doc_intelligence_extract as f; import json; print(json.dumps(f('fixtures/private/register_page.png'), indent=2)[:3000])"
```

Then re-run `py -3.12 -m pytest -q`: the same tests now execute against the real
cached response, because replay picks up the cache file automatically.

## 2. ⚠️ ACTION FOR MAIN — `config.DOC_INTEL` paths are wrong

`config.py` is main's file, so this branch did not touch it. The documented
product is **doc-digitization**, not document-intelligence:

| `config.DOC_INTEL` (stale) | Actual (docs.sarvam.ai, verified 2026-07-26) |
|---|---|
| `POST /api/document-intelligence/initialize` | `POST /doc-digitization/job/v1` |
| `POST /api/document-intelligence/get-upload-links` | `POST /doc-digitization/job/v1/upload-files` |
| `POST /api/document-intelligence/start` | `POST /doc-digitization/job/v1/{job_id}/start` |
| `GET /api/document-intelligence/status` | `GET /doc-digitization/job/v1/{job_id}/status` |
| `POST /api/document-intelligence/get-download-links` | `POST /doc-digitization/job/v1/{job_id}/download-files` |

Corrected constants live in `sarvam_client.DOC_DIGITIZATION`; nothing imports
`DOC_INTEL` any more. Copy them into `config.py` + IDEA_SCOPE.md §5 when
convenient — **nothing is blocked on it.**

Also verified today, for §5:
- chat: `POST /v1/chat/completions`, model ids `sarvam-105b` / `sarvam-30b`
  (both confirmed valid), and `response_format` supports
  `text | json_object | json_schema`.
- **Input must be `.pdf` or `.zip`, exactly one file, ≤200 MB, ≤10 pages.** A
  bare `.png`/`.jpg` is rejected — `_prepare_upload` zips the photo with no
  re-encoding, so the degradation we test against reaches the model intact.
- There is **no synchronous vision endpoint**. The async job is the only route.

## 3. What is still unverified (needs the key)

1. **The content of the downloaded result file.** We request
   `output_format: json`; `pipeline._pages` accepts a bare string,
   `{text|markdown|md|content|html}`, or `{pages: [...]}` of either, so any
   plausible shape lands. The four entries in `offline_sample.json` deliberately
   use four different shapes to keep that path honest.
2. **Whether per-region confidence exists at all.** Nothing in the docs promises
   it. See §4 — this is the interesting one.
3. The `x-ms-blob-type: BlockBlob` header on Azure presigned PUTs. Harmless if
   unnecessary; if the first real call 400s on the upload, drop that line first.

## 4. The refusal policy does not depend on Sarvam returning a confidence

This was the real design risk. `src/extraction/confidence.py` uses an API
confidence **if one is returned**, and otherwise earns a number from evidence
that is actually on the page: does the value have the shape the field takes
(a date that parses, an area that reads `<n> एकड़ <n> गुंठा`, a survey number
`SN-142/2`, a name of 1–3 tokens), does it appear verbatim, does the page repeat
it, does it carry OCR noise. Ceiling 0.95 — we never saw the paper.

Tuned against `REFUSE_BELOW = 0.75`: a clean well-shaped value lands at 0.85–0.90
and is READ; a shape-broken one lands at 0.40 and is REFUSED. On the card-87
page that draws the line exactly where DATASET.md says it should:

| Field | Value as extracted | Conf | Outcome |
|---|---|---:|---|
| `survey_no` | `SN-143` | 0.85 | read |
| `khata_no` | `१३` | 0.90 | read |
| `father_name` | `रामय्या` | 0.85 | read |
| `owner_name` | `सुशीला देवी सुशीला बाई` | 0.40 | **refused** — cell holds two names |
| `plot_area` | `०५ गुठा` | 0.40 | **refused** — stamp ate the column |
| `deadline` (slip) | `14/08/2026` | 0.90 | read → `2026-08-14` |
| `deadline` (bank) | `01.09.2026` | 0.80 | read, with the day-first assumption recorded |

The struck-through owner is refused rather than adjudicated — DATASET.md's "the
system must not silently pick one" — and both candidate names survive in the
refusal's `SourceRef.quote`, which is what **feat/register** needs to crop and
show. Refusal reasons ride in `ObligationDraft.raw_excerpt`, because the FROZEN
contract has no field for them.

## 5. What feat/register and feat/ui can rely on

- Refused readings always keep a `SourceRef` with the verbatim page words, so a
  crop can be located from the quote even when `bbox` is `None` (the offline
  stand-in carries no bboxes; a real response may).
- `SourceRef.bbox` is populated when the API supplies one on the region.
- Original uploaded pixels are kept at
  `fixtures/raw/uploads/<case_id>/<filename>` — not tempfile'd away — precisely
  so crops can be generated after the request returns.
- `raw_excerpt` holds provenance (`offline-sample:…` vs `sarvam-doc-digitization`),
  the classification evidence, the row-selection reason, and every refusal
  reason. It is safe to surface in the UI.

## 6. Files this branch owns and changed

| File | What |
|---|---|
| `src/sarvam_client.py` | job flow, offline replay, raw caching, `chat_json` |
| `src/extraction/pipeline.py` | drafts, quote gate, doc typing, row selection |
| `src/extraction/confidence.py` | the honest confidence model |
| `src/extraction/prompts.py` | normalisation prompt + requirement-key vocabulary |
| `src/extraction/offline_sample.json` | labelled stand-in (NOT a real capture) |
| `tests/test_extraction.py` | 14 tests, no key needed |
| `src/app.py::create_from_uploads` | the sanctioned one-function exception |

`POST /api/case` now runs the real pipeline. With no key and no `SARVAM_OFFLINE`
it returns **503 with the reason** rather than falling back to fixture data — a
demo that shows canned readings while implying they came off the wire is the one
failure this product cannot survive. The operator's fallback stays the explicit
`POST /api/case/fixture/demo`, which is untouched and still green.

## 7. Demo-day note

`SARVAM_OFFLINE=1` makes the upload flow work with no network at all, using the
stand-in. That is a legitimate fallback **only if it is described as one** —
`raw_excerpt` says `offline-sample:…` on every draft, and the honest line is
"this is a recorded response, not a live call".
