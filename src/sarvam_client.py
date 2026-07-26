"""Sarvam API client. Owned by feat/extraction (with feat/voice adding TTS/translate).

VERIFIED (2026-07-26, docs.sarvam.ai api-reference pages fetched today): base URL,
auth header, and the FULL Document Intelligence job flow — paths, request bodies
and response field names. See DOC_DIGITIZATION below.

⚠️ REPORT TO MAIN — `config.DOC_INTEL` paths are WRONG. The documented product is
"doc-digitization", not "document-intelligence":

    config.DOC_INTEL (stale)                      actual (docs.sarvam.ai)
    /api/document-intelligence/initialize      -> POST /doc-digitization/job/v1
    /api/document-intelligence/get-upload-links-> POST /doc-digitization/job/v1/upload-files
    /api/document-intelligence/start           -> POST /doc-digitization/job/v1/{job_id}/start
    /api/document-intelligence/status          -> GET  /doc-digitization/job/v1/{job_id}/status
    /api/document-intelligence/get-download-links -> POST /doc-digitization/job/v1/{job_id}/download-files

config.py belongs to main, so this file carries the corrected constants and main
copies them across (IDEA_SCOPE.md §5). Nothing here imports DOC_INTEL any more.

## The job flow, as documented
  1. POST /doc-digitization/job/v1
       body {"job_parameters": {"language": "hi-IN", "output_format": "md|html"}}
       (job_parameters is REQUIRED; "json" is NOT a valid output_format)
       -> 202 {"job_id", "job_state", "job_parameters", "storage_container_type"}
  2. POST /doc-digitization/job/v1/upload-files
       body {"job_id": ..., "files": ["<one filename>"]}
       -> {"upload_urls": {"<filename>": {"file_url": "<presigned>", "file_metadata": ...}},
           "job_state", "storage_container_type"}
     ⚠️ EXACTLY ONE file, and it must be **.pdf or .zip** — a bare .png/.jpg is
     rejected. `_prepare_upload` wraps photos in a ZIP with no re-encoding.
  3. PUT the bytes to file_url  (Azure presigned blobs also need x-ms-blob-type)
  4. POST /doc-digitization/job/v1/{job_id}/start          body {}
  5. GET  /doc-digitization/job/v1/{job_id}/status         poll until
     job_state in {Completed, PartiallyCompleted, Failed}
  6. POST /doc-digitization/job/v1/{job_id}/download-files body {}
       -> {"download_urls": {"<filename>": {"file_url": ...}}}; GET each file_url.

## ✅ M0 VERIFIED BY ONE REAL CALL — 2026-07-26, fixtures/private/register_page.png
1067x1373 PNG, whole flow, 9.4s wall clock. Where the docs were WRONG:

  * `output_format` accepts **'html' or 'md' ONLY**. Asking for 'json' 400s:
        body.job_parameters.output_format : Input should be 'html' or 'md'
    The docs list json. It does not exist. Default here is now 'md'.
  * `job_parameters` is **REQUIRED**. An empty body 400s:
        body.job_parameters : Field required
    The docs say all fields are optional.
  * the create response carries three fields the docs omit — `prompt_type`,
    `prompt`, `source` — and `storage_container_type` came back "Azure_V1".
  * `job_id` is not a bare UUID: "20260726_46a20ccd-4a7d-4e5b-abcb-cc6571da48b2".
  * `x-ms-blob-type: BlockBlob` on the presigned PUT: CONFIRMED working.

### The download is a ZIP, not a document
`download_urls` has ONE entry keyed "document.zip" (whatever you uploaded),
content-type application/octet-stream. Inside:

    document.md              the whole document; tables come back as HTML
                             <table>...</table> embedded in the markdown
    metadata/page_001.json   one file per page:
      {"page_num", "image_width", "image_height", "created_at",
       "blocks": [{"block_id", "coordinates": {"x1","y1","x2","y2"},  <- PIXELS
                   "layout_tag": "headline|table|...", "confidence": 0.91,
                   "reading_order": 1, "text": "..."}]}

### Per-region confidence EXISTS — and is coarser than it looks
Blocks are LAYOUT regions, not fields: our register page came back as two
blocks, a headline at 0.583 and the ENTIRE table at 0.912. So a block
confidence must never be handed to a field read out of that block — doing so
would stamp 0.912 on the stamp-occluded area cell and read a value nobody can
read. `_normalised_blocks` passes the number through; `extraction/pipeline.py`
uses it only as a CEILING unless the block is a tight match for the field.

Raw responses, the result zip and every unpacked member are cached to
fixtures/raw/ — that cache is the demo's network fallback and the shape record.
"""
from __future__ import annotations

import io
import json
import os
import pathlib
import time
import zipfile

import httpx

from .config import (AUTH_HEADER, CHAT_MODEL, SARVAM_API_KEY, SARVAM_BASE_URL,
                     TRANSLATE_MODEL, TTS_MODEL)

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "fixtures" / "raw"          # git-ignored response cache
OFFLINE_SAMPLE = pathlib.Path(__file__).resolve().parent / "extraction" / "offline_sample.json"

# Corrected, documentation-verified paths (see module docstring).
DOC_DIGITIZATION = {
    "create": "/doc-digitization/job/v1",
    "upload_files": "/doc-digitization/job/v1/upload-files",
    "start": "/doc-digitization/job/v1/{job_id}/start",
    "status": "/doc-digitization/job/v1/{job_id}/status",
    "download_files": "/doc-digitization/job/v1/{job_id}/download-files",
}
TERMINAL_STATES = {"Completed", "PartiallyCompleted", "Failed"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}

POLL_INTERVAL_S = 3.0
POLL_TIMEOUT_S = 240.0


class SarvamUnavailable(RuntimeError):
    """No key and no sanctioned replay — refuse rather than fake a reading."""


def _headers() -> dict:
    if not SARVAM_API_KEY:
        raise SarvamUnavailable("SARVAM_API_KEY is not set (.env)")
    return {AUTH_HEADER: SARVAM_API_KEY}


def offline_mode() -> bool:
    """Read at call time, not import time — tests toggle it per case."""
    return os.getenv("SARVAM_OFFLINE", "").strip() not in ("", "0", "false", "False")


# VERIFIED M0: sarvam-105b is a REASONING model. It bills thinking against the
# same budget as the answer, and the default cap (2048) is not enough for a
# page-sized prompt: the call returns 200 with finish_reason "length" and
# **content: null** after ~6.4k characters of reasoning_content. Our normalisation
# prompt needed ~2.9k completion tokens end to end. Too low here does not look
# like an error — it looks like the model had nothing to say.
#
# 4096 is a HARD CEILING on this account, not a choice:
#   max_tokens (5000) exceeds the maximum allowed for sarvam-105b for your
#   subscription tier (starter): 4096. Please reduce max_tokens or upgrade.
# So the headroom over a page-sized prompt is ~1.2k tokens. A longer page can
# still exhaust it — which is why extraction treats a failed normalisation as a
# degraded draft (deterministic reader only), never as a failed run.
CHAT_MAX_TOKENS = 4096


def chat(messages: list[dict], **kw) -> str:
    """Sarvam-105B chat completion — used for obligation normalisation.
    Verified: POST /v1/chat/completions, model ids sarvam-105b / sarvam-30b,
    response_format supports text | json_object | json_schema. The message also
    carries `reasoning_content`, `refusal` and `tool_calls`."""
    kw.setdefault("max_tokens", CHAT_MAX_TOKENS)
    r = httpx.post(f"{SARVAM_BASE_URL}/v1/chat/completions", headers=_headers(),
                   json={"model": CHAT_MODEL, "messages": messages, **kw}, timeout=180)
    r.raise_for_status()
    choice = r.json()["choices"][0]
    message = choice.get("message") or {}
    content = message.get("content")
    if not content:
        raise ValueError(
            "chat returned no content (finish_reason="
            f"{choice.get('finish_reason')!r}, refusal={message.get('refusal')!r}) — "
            "raise max_tokens if the reasoning ran to the cap")
    return content


def chat_json(messages: list[dict], **kw) -> dict:
    """Chat constrained to a JSON object. Raises ValueError if the model still
    returns prose — the caller must NOT try to salvage a guess out of it."""
    raw = chat(messages, response_format={"type": "json_object"}, **kw)
    text = raw.strip()
    if text.startswith("```"):                       # tolerate fenced output
        text = text.strip("`")
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"normalisation model did not return JSON: {raw[:400]}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"normalisation model returned {type(parsed).__name__}, not an object")
    return parsed


def translate(text: str, target: str = "hi-IN") -> str:
    r = httpx.post(f"{SARVAM_BASE_URL}/translate", headers=_headers(),
                   json={"input": text, "source_language_code": "auto",
                         "target_language_code": target, "model": TRANSLATE_MODEL},
                   timeout=60)
    r.raise_for_status()
    return r.json().get("translated_text", "")


def tts(text: str, lang: str = "hi-IN") -> bytes:
    """Bulbul v3 — returns audio bytes. VERIFY response field name in M0."""
    r = httpx.post(f"{SARVAM_BASE_URL}/text-to-speech", headers=_headers(),
                   json={"text": text, "target_language_code": lang, "model": TTS_MODEL},
                   timeout=120)
    r.raise_for_status()
    return r.content


# --- Document Intelligence ---------------------------------------------------

def _cache_raw(name: str, payload) -> pathlib.Path:
    """Every API response lands on disk. This is the demo's network fallback and
    the record of the real shapes (fixtures/raw/ is git-ignored)."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / name
    body = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, indent=2)
    path.write_text(body, encoding="utf-8")
    return path


def _cache_bytes(name: str, blob: bytes) -> pathlib.Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / name
    path.write_bytes(blob)
    return path


def _normalised_blocks(blocks: list, width: int, height: int) -> list[dict]:
    """Sarvam's layout blocks -> our shape. `bbox` is normalised 0-1 because the
    FROZEN SourceRef contract says so; `bbox_px` is kept alongside because
    feat/register crops with PIL and wants pixels."""
    out = []
    for b in blocks:
        if not isinstance(b, dict):
            continue
        c = b.get("coordinates") or {}
        px = [c.get("x1"), c.get("y1"), c.get("x2"), c.get("y2")]
        bbox = ([px[0] / width, px[1] / height, px[2] / width, px[3] / height]
                if width and height and all(isinstance(v, (int, float)) for v in px)
                else None)
        out.append({"text": b.get("text", ""), "confidence": b.get("confidence"),
                    "bbox": bbox, "bbox_px": px if bbox else None,
                    "layout_tag": b.get("layout_tag"),
                    "block_id": b.get("block_id"),
                    "reading_order": b.get("reading_order")})
    return out


def _parse_result(blob: bytes, stem: str) -> dict:
    """The downloaded object -> {"markdown": str, "pages": [...]}.

    Verified path is a ZIP (document.md + metadata/page_NNN.json). The other
    branches are kept because the docs describe none of this and a future
    output_format may well hand back the markdown or JSON directly.
    """
    if blob[:2] != b"PK":
        text = blob.decode("utf-8", "replace")
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return {"markdown": text, "pages": [{"page_number": 1, "text": text}]}
        return parsed if isinstance(parsed, dict) else {"pages": parsed}

    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        members = {n: zf.read(n) for n in zf.namelist()}
    for name, data in members.items():                  # keep every member on disk
        _cache_bytes(f"{stem}.result.{name.replace('/', '_')}", data)

    markdown = next((data.decode("utf-8", "replace") for name, data in members.items()
                     if name.lower().endswith((".md", ".html", ".txt"))), "")
    pages = []
    for name in sorted(n for n in members if n.lower().endswith(".json")):
        try:
            meta = json.loads(members[name].decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        blocks = _normalised_blocks(meta.get("blocks") or [],
                                    meta.get("image_width") or 0,
                                    meta.get("image_height") or 0)
        ordered = sorted(blocks, key=lambda b: b.get("reading_order") or 0)
        pages.append({"page_number": meta.get("page_num") or len(pages) + 1,
                      "text": "\n\n".join(b["text"] for b in ordered if b["text"]),
                      "image_width": meta.get("image_width"),
                      "image_height": meta.get("image_height"),
                      "blocks": blocks})
    if not pages:                                       # md only, no metadata
        pages = [{"page_number": 1, "text": markdown}]
    return {"markdown": markdown, "pages": pages}


def _prepare_upload(image_path: pathlib.Path) -> tuple[str, bytes, str]:
    """-> (upload_filename, bytes, content_type). The API takes .pdf or .zip
    only, so a photograph is zipped VERBATIM — no re-encode, no resample; the
    degradation we are testing against must reach the model intact."""
    data = image_path.read_bytes()
    suffix = image_path.suffix.lower()
    if suffix == ".pdf":
        return image_path.name, data, "application/pdf"
    if suffix == ".zip":
        return image_path.name, data, "application/zip"
    if suffix not in IMAGE_SUFFIXES:
        raise ValueError(f"unsupported input {image_path.name}: need pdf, zip, png or jpg")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(image_path.name, data)
    return f"{image_path.stem}.zip", buf.getvalue(), "application/zip"


def _offline_payload(image_path: pathlib.Path) -> dict:
    """Replay a cached response. Prefers a REAL cached response for this exact
    image (fixtures/raw/<stem>.docintel.json, written by the first live call);
    falls back to the committed hand-authored stand-in, which is labelled as
    such in every field it produces."""
    cached = RAW_DIR / f"{image_path.stem}.docintel.json"
    if cached.exists():
        payload = json.loads(cached.read_text(encoding="utf-8"))
        payload["provenance"] = f"offline-replay:{cached.as_posix()}"
        return payload

    sample = json.loads(OFFLINE_SAMPLE.read_text(encoding="utf-8"))
    docs = sample["documents"]
    entry = docs.get(image_path.stem) or docs["default"]
    return {
        "provenance": f"offline-sample:{image_path.stem if image_path.stem in docs else 'default'}",
        "offline": True,
        "source_path": image_path.as_posix(),
        "job_id": None,
        "requested": {"language": "hi-IN", "output_format": "json"},
        "documents": [entry],
        "api_trace": {},
    }


def doc_intelligence_extract(image_path: str, *, language: str = "hi-IN",
                             output_format: str = "md",
                             poll_timeout_s: float = POLL_TIMEOUT_S) -> dict:
    """One photographed page -> the raw Doc-Intelligence result, plus the trace.

    Returns:
        {"provenance": "sarvam-doc-digitization" | "offline-...",
         "offline": bool, "source_path": str, "job_id": str|None,
         "requested": {...},
         "documents": [{"file_name": str, "content": <json|str>}],
         "api_trace": {step: response_json}}          # the M0 shape record

    Set SARVAM_OFFLINE=1 to replay the cached/sample response instead of calling
    out. With no key and no SARVAM_OFFLINE we raise — a demo must never show a
    canned reading while implying it came off the wire.
    """
    path = pathlib.Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"no such page: {path}")
    if offline_mode():
        return _offline_payload(path)
    if not SARVAM_API_KEY:
        raise SarvamUnavailable(
            f"SARVAM_API_KEY is not set, so {path.name} cannot be read. "
            "Set the key in .env, or set SARVAM_OFFLINE=1 to replay the cached "
            "response (clearly marked as a replay).")

    h = _headers()
    trace: dict = {}
    with httpx.Client(timeout=120) as client:
        def _post(url: str, body: dict, step: str) -> dict:
            r = client.post(url, headers=h, json=body)
            r.raise_for_status()
            data = r.json()
            trace[step] = data
            _cache_raw(f"{path.stem}.{step}.json", data)
            return data

        created = _post(f"{SARVAM_BASE_URL}{DOC_DIGITIZATION['create']}",
                        {"job_parameters": {"language": language,
                                            "output_format": output_format}},
                        "create")
        job_id = created["job_id"]

        upload_name, blob, content_type = _prepare_upload(path)
        links = _post(f"{SARVAM_BASE_URL}{DOC_DIGITIZATION['upload_files']}",
                      {"job_id": job_id, "files": [upload_name]}, "upload_files")

        entry = links["upload_urls"][upload_name]
        put_headers = {"Content-Type": content_type}
        if str(links.get("storage_container_type", "")).startswith("Azure"):
            # UNVERIFIED: Azure presigned block-blob PUTs reject a body without
            # this header. Harmless elsewhere; remove if the first real call 400s.
            put_headers["x-ms-blob-type"] = "BlockBlob"
        put = client.put(entry["file_url"], content=blob, headers=put_headers)
        put.raise_for_status()
        trace["upload_put"] = {"status": put.status_code, "bytes": len(blob),
                               "filename": upload_name}

        _post(f"{SARVAM_BASE_URL}{DOC_DIGITIZATION['start'].format(job_id=job_id)}",
              {}, "start")

        deadline = time.monotonic() + poll_timeout_s
        status: dict = {}
        while True:
            r = client.get(
                f"{SARVAM_BASE_URL}{DOC_DIGITIZATION['status'].format(job_id=job_id)}",
                headers=h)
            r.raise_for_status()
            status = r.json()
            if status.get("job_state") in TERMINAL_STATES:
                break
            if time.monotonic() > deadline:
                _cache_raw(f"{path.stem}.status.timeout.json", status)
                raise TimeoutError(
                    f"job {job_id} still {status.get('job_state')} after "
                    f"{poll_timeout_s:.0f}s — no reading, so nothing is guessed")
            time.sleep(POLL_INTERVAL_S)
        trace["status"] = status
        _cache_raw(f"{path.stem}.status.json", status)
        if status.get("job_state") == "Failed":
            raise RuntimeError(
                f"doc-digitization job {job_id} Failed: {status.get('error_message')}")

        dl = _post(
            f"{SARVAM_BASE_URL}{DOC_DIGITIZATION['download_files'].format(job_id=job_id)}",
            {}, "download_files")

        documents = []
        for file_name, meta in (dl.get("download_urls") or {}).items():
            got = client.get(meta["file_url"])
            got.raise_for_status()
            _cache_bytes(f"{path.stem}.result.{file_name}", got.content)
            documents.append({"file_name": file_name,
                              "content": _parse_result(got.content, path.stem)})

    payload = {"provenance": "sarvam-doc-digitization", "offline": False,
               "source_path": path.as_posix(), "job_id": job_id,
               "requested": {"language": language, "output_format": output_format},
               "documents": documents, "api_trace": trace}
    # Stable name = what SARVAM_OFFLINE=1 replays next time. Free reruns, and a
    # network-outage fallback on demo day.
    _cache_raw(f"{path.stem}.docintel.json", payload)
    return payload
