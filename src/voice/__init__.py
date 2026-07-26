"""feat/voice — Hindi output. CUTTABLE if behind schedule.

Build here:
  plan_to_hindi(plan) -> short Hindi summary via sarvam_client.translate
  speak(plan) -> bytes via sarvam_client.tts (bulbul:v3), served at
  GET /api/case/{id}/audio; web adds one <audio> play button.

Acceptance: the demo plan plays aloud in Hindi. Nothing else. No STT, no
conversation — that would be Voice Experience scope, and our scored parameter
is Document Intelligence.
"""
