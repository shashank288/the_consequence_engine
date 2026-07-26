"""feat/extraction — photographed page -> ObligationDraft.

Pipeline to build here:
  1. sarvam_client.doc_intelligence_extract(image) -> raw fields + confidences
  2. chat(CHAT_MODEL) normalisation: raw text -> ObligationDraft JSON
     (asked_what/asked_by/due/needs-with-QUOTES/provides/identity_fields).
     The LLM must QUOTE the words for every Requirement — no quote, no need.
  3. return list[ObligationDraft] for app.create_from_uploads

Acceptance: one real photographed doc -> a draft whose deadline field is either
read-with-confidence or REFUSED — never silently wrong. Cache every raw API
response to fixtures/raw/ so reruns are free and the demo has a fallback.
"""
