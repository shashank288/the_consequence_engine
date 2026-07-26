"""LIVE end-to-end run on the held-out page — the real MVP proof.

Uploads an unseen page through POST /api/case (real Sarvam doc-digitization job),
then reports the numbers IDEA_SCOPE §6 Impact and docs/IMPACT.md ask for.

    py -3.12 -m scripts.live_holdout [path]      # needs SARVAM_API_KEY
"""
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from src.app import app
from src.config import SARVAM_API_KEY

page = sys.argv[1] if len(sys.argv) > 1 else "fixtures/private/register_holdout.png"
p = pathlib.Path(page)
if not p.exists():
    sys.exit(f"missing {p} — generate with: py -3.12 scripts/make_register_page.py --seed 13 --out {p}")
if not SARVAM_API_KEY:
    sys.exit("SARVAM_API_KEY not set in .env — this script only does the LIVE path")

print(f"uploading {p.name} ({p.stat().st_size // 1024} KB) to POST /api/case — live Sarvam job\n")
t0 = time.time()
with TestClient(app) as c:
    r = c.post("/api/case", files={"files": (p.name, p.read_bytes(), "image/png")})
    elapsed = time.time() - t0
    print(f"HTTP {r.status_code}  in {elapsed:.1f}s")
    if r.status_code != 200:
        sys.exit(f"FAILED: {str(r.json())[:500]}")

    case = r.json()
    plan = case["plan"]
    readings = [f for d in case["drafts"]
                for f in ([d.get("due"), d.get("amount")] + (d.get("identity_fields") or []))
                if f]
    read = [f for f in readings if f["status"] == "read"]
    refused = [f for f in readings if f["status"] == "refused"]
    guessed = [f for f in refused if f.get("value") is not None]

    print(f"\n{'=' * 62}\nHELD-OUT PAGE — LIVE RESULT\n{'=' * 62}")
    print(f"  consequence-bearing fields seen : {len(readings)}")
    print(f"  read with a confidence          : {len(read)}")
    print(f"  REFUSED rather than guessed     : {len(refused)}")
    print(f"  refused fields still carrying a value (MUST BE 0) : {len(guessed)}")
    print(f"  refusals with a crop for review : "
          f"{sum(1 for f in refused if (f.get('source') or {}).get('crop_path'))}")
    print(f"  contradictions / mismatches     : {len(plan['mismatches'])}")
    print(f"  blocking edges (quoted)         : {len(plan['edges'])}")

    print(f"\n  READ:")
    for f in read:
        print(f"    {f['name']:<22} {f['confidence']:.2f}  {str(f['value'])[:44]}")
    print(f"\n  REFUSED (routed to a human, never guessed):")
    for f in refused:
        q = ((f.get("source") or {}).get("quote") or "")
        why = q.split("REFUSED (")[-1].split(")")[0] if "REFUSED (" in q else "low confidence"
        print(f"    {f['name']:<22} {f['confidence']:.2f}  [{why}]")

    print(f"\n  NEXT SINGLE ACTION:\n    {plan['next_single_action']}")
    print(f"\n{'=' * 62}")
    print("  Paste these into docs/IMPACT.md 'Our own number' and IDEA_SCOPE §6.")
    print(f"  Headline: on an unseen page, {len(refused)} consequence-bearing fields")
    print(f"  were refused and routed; {len(guessed)} were guessed wrong.\n")
