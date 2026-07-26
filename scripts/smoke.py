"""End-to-end smoke test of the whole app — the demo runbook as code.

Runs the real FastAPI app in-process (no port, no network, no Sarvam key) and
walks the exact 2-minute demo path. If this passes, the demo works.

    py -3.12 -m scripts.smoke
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from src.app import app

ok, fail = [], []


def check(label, cond, detail=""):
    (ok if cond else fail).append(label)
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + (f"  — {detail}" if detail else ""))


with TestClient(app) as c:
    print("\n[1] health + static UI")
    check("GET /api/health", c.get("/api/health").json().get("ok") is True)
    idx = c.get("/")
    check("GET / serves the UI", idx.status_code == 200 and "Consequence Engine" in idx.text)

    print("\n[2] load demo case  (demo step 1)")
    r = c.post("/api/case/fixture/demo")
    check("fixture loads", r.status_code == 200, f"status {r.status_code}")
    case = r.json()
    cid, plan = case["id"], case["plan"]
    states = {i["obligation_id"]: i for i in plan["items"]}
    check("ONE next single action", bool(plan["next_single_action"]),
          repr(plan["next_single_action"])[:70])
    check("O1 actionable, order 1", states["O1"]["state"] == "actionable" and states["O1"]["order"] == 1)
    check("O2 blocked", states["O2"]["state"] == "blocked")
    check("O4 folded as duplicate", states["O4"]["state"] == "duplicate")
    check("O5 in unknown bucket", states["O5"]["state"] == "unknown")

    print("\n[3] blocking edge carries a quoted reason  (demo step 2 — Creativity)")
    e = next((x for x in plan["edges"] if x["blocked_id"] == "O2"), None)
    check("O2 blocked by O1", e is not None and e["blocker_id"] == "O1")
    check("reason quotes the page", e and "must match record-of-rights" in e["reason"])
    check("evidence cites >=2 sources", e and len(e["evidence"]) >= 2,
          f"{len(e['evidence']) if e else 0} refs")

    print("\n[4] refusal routed with a crop  (demo step 6 — Delight + Doc Intelligence)")
    ref = next((x for x in plan["refusals"] if x["name"] == "plot_area"), None)
    check("plot_area refused, not guessed", ref is not None and ref["value"] is None)
    cp = (ref or {}).get("source", {}).get("crop_path")
    check("crop_path present", bool(cp), str(cp))
    if cp:
        img = c.get("/" + cp.lstrip("/"))
        check("crop image is actually served", img.status_code == 200 and
              img.headers.get("content-type", "").startswith("image"),
              f"status {img.status_code}, {len(img.content)} bytes")

    print("\n[5] correction propagates  (demo step 4 — Memory)")
    r = c.post(f"/api/case/{cid}/correct", json={"doc_id": "record_page_1947",
                                                 "field_name": "owner_name",
                                                 "new": "SUSHILA DEVI"})
    check("correct returns 200", r.status_code == 200, f"status {r.status_code}")
    d = r.json().get("diff", {})
    check("diff.summary is printable", bool(d.get("summary")), str(d.get("summary"))[:80])
    check("propagated_to names obligations", bool(d.get("propagated_to")), str(d.get("propagated_to")))
    check("mismatch cleared", len(d.get("mismatches_cleared") or []) >= 1)

    print("\n[6] bad correction target refuses with a menu")
    r = c.post(f"/api/case/{cid}/correct", json={"doc_id": "counter_slip",
                                                 "field_name": "owner_name", "new": "X"})
    check("404 with available_targets", r.status_code == 404 and
          "available_targets" in str(r.json()))

    print("\n[7] mark blocker done -> re-sequence  (demo step 5 — JTBD)")
    r = c.post(f"/api/case/{cid}/status/record_name_matches_id")
    p2 = r.json()["plan"]
    s2 = {i["obligation_id"]: i for i in p2["items"]}
    check("O1 now done", s2["O1"]["state"] == "done")
    check("O2 now actionable", s2["O2"]["state"] == "actionable")
    check("next action moved to O2", "mutation" in (p2["next_single_action"] or "").lower(),
          repr(p2["next_single_action"])[:70])

    print("\n[8] reload-resume from disk  (Memory L4)")
    g = c.get(f"/api/case/{cid}").json()
    check("case survives reload", g["plan"]["items"] is not None)
    check("correction_log persisted", len(g.get("correction_log") or []) >= 1)
    check("GET /api/cases lists it", any(x["id"] == cid for x in c.get("/api/cases").json()))

    print("\n[9] reset for the next judge  (demo step 7 / M5)")
    r = c.post(f"/api/case/{cid}/reset")
    s3 = {i["obligation_id"]: i for i in r.json()["plan"]["items"]}
    check("back to as-loaded", s3["O1"]["state"] == "actionable" and s3["O2"]["state"] == "blocked")

    print("\n[10] upload path status")
    r = c.post("/api/case", files={"files": ("t.png", b"\x89PNG\r\n\x1a\n", "image/png")})
    check("upload wired or honest 501", r.status_code in (200, 501),
          "501 = feat/extraction not merged; UI falls back to demo case"
          if r.status_code == 501 else "extraction live")

print(f"\n{'=' * 58}\n  {len(ok)} passed, {len(fail)} failed")
if fail:
    print("  FAILED: " + "; ".join(fail))
    sys.exit(1)
print("  DEMO PATH IS RUNNABLE END TO END\n")
