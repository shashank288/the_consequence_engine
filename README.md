# ⚖️ The Consequence Engine

**Sarvam Epoch Buildathon 2026 · Document Intelligence**

After a death in an Indian family, transferring the land record (mutation) fails
on tiny mismatches between decades-old handwritten registers and modern IDs —
rejected applications, repeat visits, touts. This tool photographs the whole
paper stack and returns **one ordered plan with exactly one next action**:

- **A sequencer, not an explainer** — blocking dependencies are derived from the
  documents' own words; every edge quotes the lines it rests on
- **Refusal-first** — an unreadable field (seal, overwriting, faded ink) is
  refused and routed to a human with a cropped image, never guessed
- Duplicates folded, unclassifiable items surfaced in an **unknown bucket**
- Corrections propagate; the case resumes after reload; Hindi audio summary

Built on **Sarvam Vision / Document Intelligence** (Akshar), sarvam-105b,
sarvam-translate, bulbul:v3.

## Quickstart
```bash
pip install -r requirements.txt
python -m pytest -q
uvicorn src.app:app --port 8000   # → http://localhost:8000 → "Load demo case"
```

See `IDEA_SCOPE.md` (build control plane) and `CLAUDE.md` (agent/branch rules).
