"""Sarvam API client. Owned by feat/extraction (with feat/voice adding TTS/translate).

VERIFIED (2026-07-26, docs.sarvam.ai): base URL, auth header, endpoint paths.
NOT YET VERIFIED: exact request/response JSON shapes of the Document
Intelligence job API — M0's first task is one real call with one real image.

Doc Intelligence is an ASYNC JOB flow:
  1. POST /api/document-intelligence/initialize        -> job id
  2. POST /api/document-intelligence/get-upload-links  -> presigned upload URL(s)
  3. PUT file to the upload URL
  4. POST /api/document-intelligence/start
  5. GET  /api/document-intelligence/status            (poll)
  6. POST /api/document-intelligence/get-download-links -> result JSON
"""
from __future__ import annotations

import httpx

from .config import (AUTH_HEADER, CHAT_MODEL, DOC_INTEL, SARVAM_API_KEY,
                     SARVAM_BASE_URL, TRANSLATE_MODEL, TTS_MODEL)


def _headers() -> dict:
    if not SARVAM_API_KEY:
        raise RuntimeError("SARVAM_API_KEY is not set (.env)")
    return {AUTH_HEADER: SARVAM_API_KEY}


def chat(messages: list[dict], **kw) -> str:
    """Sarvam-105B chat completion — used for obligation normalisation."""
    r = httpx.post(f"{SARVAM_BASE_URL}/v1/chat/completions", headers=_headers(),
                   json={"model": CHAT_MODEL, "messages": messages, **kw}, timeout=120)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


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


def doc_intelligence_extract(image_path: str) -> dict:
    """M0 CRITICAL: run one photographed page through the async job flow.
    Implement + verify shapes here first; then feat/extraction builds
    extraction/pipeline.py mapping the raw result -> ObligationDraft."""
    raise NotImplementedError("M0: verify job-API shapes with one real call")
