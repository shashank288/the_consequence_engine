# AGENT BRIEF — feat/voice  ⚠️ FIRST TO BE CUT

Read `../../IDEA_SCOPE.md` §7 and `../../CLAUDE.md` first.

## Mission
One button that reads the plan aloud in Hindi. That is the entire scope.

**Our scored Sarvam parameter is Document Intelligence.** Voice earns us **zero
extra rubric points** — it exists only so a non-reading user can actually receive
the plan, which supports the declared job. If any other branch is behind, this one
is cut without discussion (IDEA_SCOPE.md §8 M4).

## Files you own
- `src/voice/`
- `src/app.py` — one new route only: `GET /api/case/{id}/audio`
- `web/index.html` — one `<audio>` element and one button. **Coordinate with
  feat/ui before touching it; if they are mid-edit, hand them the snippet instead.**

**Forbidden:** everything else.

## Tasks
1. `plan_to_hindi(plan) -> str` — build a **short** Hindi summary via
   `sarvam_client.translate(..., target="hi-IN")`:
   - the one next action and where to do it
   - the count of blocked items and the single most important reason
   - the count of refused fields, phrased as *"these need a human to check"*

   **Under 60 words.** A judge will not listen to 3 minutes of audio.

2. `speak(text) -> bytes` — `sarvam_client.tts(text, "hi-IN")` using `bulbul:v3`.
   **Verify the exact model id string and the response format with one real call
   before wiring it** (config.py marks it VERIFY).

3. Cache generated audio per case id. Never regenerate during the demo — a live
   TTS call that hangs on venue wifi costs us the demo.

## Rules
- **Never make the audio blocking.** If TTS fails, the button disables with a
  quiet message; the plan must render regardless.
- No speech input, no conversation, no STT. That is Voice Experience scope and we
  did not select it.
- Pre-generate the demo case's audio and commit it as a fallback file.

## Acceptance test
> The demo case's plan plays as intelligible Hindi in under 20 seconds, and the
> page works normally with the audio route unavailable.

## Verify
```bash
py -3.12 -m uvicorn src.app:app --port 8000
```
Merge **last**. If it is not merged by 15:40, it does not ship.
