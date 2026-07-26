"""Central config. Verified values only — anything marked VERIFY is an M0 task."""
import os

SARVAM_BASE_URL = os.getenv("SARVAM_BASE_URL", "https://api.sarvam.ai")
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
AUTH_HEADER = "api-subscription-key"          # verified: docs.sarvam.ai quickstart

# Refusal policy (the product's spine). A consequence-bearing field below this
# confidence is REFUSED and routed to escalation — never guessed.
REFUSE_BELOW = 0.75
CONSEQUENTIAL_FIELDS = {"deadline", "amount", "owner_name", "plot_no", "survey_no", "name", "date"}

# Models — verified on docs.sarvam.ai/api/getting-started/models (2026-07-26)
CHAT_MODEL = "sarvam-105b"                    # VERIFY exact id string in M0 call
TRANSLATE_MODEL = "sarvam-translate"          # 23 langs
TTS_MODEL = "bulbul:v3"                       # VERIFY exact id string in M0 call
TTS_LANG = "hi-IN"

# Document Intelligence async job API — paths verified via docs.sarvam.ai/llms.txt
# (request/response shapes NOT yet verified — M0 task, see IDEA_SCOPE.md M0)
DOC_INTEL = {
    "init": "/api/document-intelligence/initialize",
    "upload_links": "/api/document-intelligence/get-upload-links",
    "start": "/api/document-intelligence/start",
    "status": "/api/document-intelligence/status",
    "download_links": "/api/document-intelligence/get-download-links",
}
# Limits (verified): Vision API 10 PDF pages / 200 MB; Akshar Studio 50 MB / 10 pages.

CASE_DB = os.getenv("CASE_DB", "cases.json")  # feat/case-memory may move to SQLite
