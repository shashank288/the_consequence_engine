"""Central config. Verified values only — anything marked VERIFY is an M0 task."""
import os
import pathlib

# Load .env so a plain `uvicorn`, `pytest` or `python -m scripts.*` sees the key.
# Without this, only `uvicorn --env-file .env` worked. Never commit a real key —
# .env is gitignored; .env.example must stay empty.
try:
    from dotenv import load_dotenv

    load_dotenv(pathlib.Path(__file__).resolve().parents[1] / ".env")
except ImportError:  # python-dotenv ships with uvicorn[standard]; degrade quietly
    pass

SARVAM_BASE_URL = os.getenv("SARVAM_BASE_URL", "https://api.sarvam.ai")
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
AUTH_HEADER = "api-subscription-key"          # verified: docs.sarvam.ai quickstart

# Refusal policy (the product's spine). A consequence-bearing field below this
# confidence is REFUSED and routed to escalation — never guessed.
REFUSE_BELOW = 0.75
CONSEQUENTIAL_FIELDS = {"deadline", "amount", "owner_name", "plot_no", "survey_no", "name", "date"}

# Models — verified against the LIVE API in M0 (2026-07-26)
CHAT_MODEL = "sarvam-105b"
TRANSLATE_MODEL = "sarvam-translate"          # 23 langs
TTS_MODEL = "bulbul:v3"
TTS_LANG = "hi-IN"

# sarvam-105b is a REASONING model and bills thinking against the answer budget.
# At the old 2048 default it returns HTTP 200 with content=null and
# finish_reason="length" — a silent failure that looks like an empty answer.
# Hard ceiling on the starter tier is 4096; our prompt needs ~2.9k completion.
CHAT_MAX_TOKENS = 4096

# Document Intelligence async job flow — CORRECTED IN M0 BY CALLING THE API.
# The documented /api/document-intelligence/* family DOES NOT EXIST. Live paths:
DOC_DIGITIZATION = {
    "create": "/doc-digitization/job/v1",
    "upload_files": "/doc-digitization/job/v1/upload-files",
    "start": "/doc-digitization/job/v1/{job_id}/start",
    "status": "/doc-digitization/job/v1/{job_id}/status",
    "download_files": "/doc-digitization/job/v1/{job_id}/download-files",
}
DOC_INTEL = DOC_DIGITIZATION                  # back-compat alias; prefer the above

# Also verified live, contradicting the published docs:
#  - output_format accepts only 'html' or 'md'. 'json' 400s.
#  - job_parameters is REQUIRED (docs say optional); {} 400s.
#  - the download is a ZIP (document.zip) holding document.md + metadata/page_XXX.json;
#    tables arrive as HTML <table> inside the markdown; block coords are PIXELS.
#  - input must be .pdf or .zip, exactly one file — a bare PNG is rejected.
#  - the presigned PUT requires header x-ms-blob-type: BlockBlob (Azure_V1).
#  - there is NO synchronous vision endpoint; the async job is the only route.
# Limits: 200 MB / 10 pages per file (API); Akshar Studio 50 MB / 10 pages.
#
# Confidence is scored PER LAYOUT BLOCK, not per field. A whole table can return
# 0.912 — treat a block score as a CEILING for fields read out of it, never as a
# verdict, or a stamp-occluded cell inherits the table's confidence.

CASE_DB = os.getenv("CASE_DB", "cases.json")  # feat/case-memory may move to SQLite
