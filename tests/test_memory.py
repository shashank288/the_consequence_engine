"""Memory & Context acceptance tests (M4). Run: py -3.12 -m pytest -q

No Sarvam key, no network: the demo fixture plus a temp JSON store.

Acceptance test being proved here (docs/agents/feat-case-memory.md):
correct owner_name once → the cosmetic mismatch clears, propagated_to names the
affected obligations, the plan re-sequences, and the same case reloaded from disk
in a FRESH store instance shows the corrected state.
"""
import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.case_store import (CaseStore, CorrectionTargetNotFound, apply_correction,
                            case_meta, correction_targets, list_cases, load_case,
                            reset_case, save_case)
from src.contracts import Case
from src.sequencer.core import build_plan

FIXTURE = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "case_demo.json"
RECORD_DOC = "record_page_1947"


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Never touch the real cases.json — CASE_DB is resolved per call."""
    db = tmp_path / "cases.json"
    monkeypatch.setenv("CASE_DB", str(db))
    return db


def _fresh_case(case_id: str = "demo-test") -> Case:
    case = Case.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))
    case.id = case_id
    case.plan = build_plan(case)
    return case


def _states(case: Case) -> dict:
    return {i.obligation_id: i for i in case.plan.items}


# --------------------------------------------------------------- 1. propagation

def test_correction_clears_mismatch_and_reports_propagation():
    case = _fresh_case()
    assert any(m.field_name == "owner_name" for m in case.plan.mismatches)

    case, correction, diff = apply_correction(case, RECORD_DOC, "owner_name", "SUSHILA DEVI")

    # the mismatch is gone from the re-derived plan
    assert not [m for m in case.plan.mismatches if m.field_name == "owner_name"]

    # propagated_to is diff-computed and names BOTH sides of the cleared mismatch:
    # O1 carries the corrected reading, O2's blocking edge lost its mismatch evidence
    assert correction.propagated_to == diff["propagated_to"]
    assert "O1" in correction.propagated_to and "O2" in correction.propagated_to
    assert correction.old == "Sushila D." and correction.new == "SUSHILA DEVI"

    cleared = diff["mismatches_cleared"]
    assert [m["field_name"] for m in cleared] == ["owner_name"]
    assert cleared[0]["classification"] == "cosmetic"
    assert cleared[0]["obligations"] == ["O1", "O2"]

    # the diff explains itself in one printable sentence for the UI
    assert "owner_name" in diff["summary"] and "mismatch on owner_name" in diff["summary"]

    # every reported obligation carries the reason it was touched
    reasons = {o["obligation_id"]: o["changes"] for o in diff["obligations"]}
    assert any("mismatch resolved" in c for c in reasons["O1"])
    assert any("evidence for the O1 → O2 edge changed" in c for c in reasons["O2"])

    # untouched obligations are NOT claimed
    assert "O5" not in correction.propagated_to


def test_propagation_is_not_guessed_from_doc_id():
    """O3/O4 quote no corrected field — a doc-id sweep would over-claim them."""
    case = _fresh_case()
    _, correction, _ = apply_correction(case, RECORD_DOC, "owner_name", "SUSHILA DEVI")
    assert "O3" not in correction.propagated_to
    assert "O4" not in correction.propagated_to


def test_correction_resolves_a_refusal():
    case = _fresh_case()
    assert [r.name for r in case.plan.refusals] == ["plot_area"]

    case, correction, diff = apply_correction(case, RECORD_DOC, "plot_area", "2 acre 30 gunta")

    assert case.plan.refusals == []                       # escalation queue drains
    assert [r["name"] for r in diff["refusals_cleared"]] == ["plot_area"]
    assert correction.propagated_to == ["O1"]
    # `old` is the sub-threshold reading the plan was refusing to use (0.55), kept
    # on the record so the superseded value stays visible
    assert correction.old == "2 acre 13 gunta"
    assert diff["patched_readings"][0]["old_confidence"] == 0.55
    field = next(f for f in case.drafts[0].identity_fields if f.name == "plot_area")
    assert (field.status, field.confidence) == ("read", 1.0)


def test_correction_reaches_the_doc_a_reading_came_from():
    """O2 carries an owner_name read off aadhaar_heir, not off its own doc."""
    case = _fresh_case()
    case, correction, _ = apply_correction(case, "aadhaar_heir", "owner_name", "SUSHILA D")
    assert "O2" in correction.propagated_to
    assert next(f for f in case.drafts[1].identity_fields).value == "SUSHILA D"


def test_unknown_target_is_refused_not_silently_dropped():
    case = _fresh_case()
    with pytest.raises(CorrectionTargetNotFound) as exc:
        apply_correction(case, "counter_slip", "owner_name", "X")
    assert case.corrections == []                          # nothing recorded
    targets = {(t["doc_id"], t["field_name"]) for t in exc.value.available}
    assert (RECORD_DOC, "owner_name") in targets           # the menu names the real one
    assert ("aadhaar_heir", "owner_name") in targets
    assert {(t["doc_id"], t["field_name"]) for t in correction_targets(case)} == targets


def test_resequence_after_status_lookup_is_reported():
    """Same diff machinery over a state change: O1 done → O2 becomes the action."""
    case = _fresh_case()
    before = case.plan
    case.done_keys = ["record_name_matches_id"]
    case.plan = build_plan(case)
    from src.case_store import diff_plans
    diff = diff_plans(case, before, case.plan)
    assert "unblocked O2" in diff["plan_summary"]
    moved = {o["obligation_id"]: (o["state_before"], o["state_after"])
             for o in diff["obligations"]}
    assert moved["O1"][1] == "done" and moved["O2"] == ("blocked", "actionable")
    assert diff["next_single_action_after"] != diff["next_single_action_before"]


# ------------------------------------------------------------- 2. reload resume

def test_reload_in_a_fresh_store_resumes_the_identical_plan():
    case = _fresh_case("demo-reload")
    save_case(case)

    reloaded = CaseStore().load("demo-reload")             # fresh instance, disk truth
    assert reloaded is not None
    assert reloaded.plan.model_dump() == case.plan.model_dump()
    assert reloaded.model_dump() == case.model_dump()
    # and the plan is still the one the sequencer would derive
    assert build_plan(reloaded).model_dump() == case.plan.model_dump()


def test_corrected_state_survives_reload():
    case = _fresh_case("demo-corrected")
    case, correction, diff = apply_correction(case, RECORD_DOC, "owner_name", "SUSHILA DEVI")
    save_case(case)
    from src.case_store import log_correction
    log_correction(case.id, {"correction": correction.model_dump(), "diff": diff})

    reloaded = CaseStore(CaseStore().path).load("demo-corrected")
    assert reloaded.plan.mismatches == []
    owner = next(f for f in reloaded.drafts[0].identity_fields if f.name == "owner_name")
    assert owner.value == "SUSHILA DEVI" and owner.confidence == 1.0
    assert len(reloaded.corrections) == 1
    assert reloaded.corrections[0].propagated_to == correction.propagated_to
    # rebuilding from the persisted drafts yields the same plan: nothing was lost
    assert build_plan(reloaded).model_dump() == reloaded.plan.model_dump()

    # the propagation diff itself is persisted beside the case (concise handoff)
    log = case_meta("demo-corrected")["correction_log"]
    assert len(log) == 1 and log[0]["diff"]["propagated_to"] == correction.propagated_to
    assert log[0]["at"]


def test_legacy_flat_store_file_still_loads(temp_db):
    """Cases written by the lite store on main must survive the format change."""
    case = _fresh_case("legacy-1")
    temp_db.write_text(json.dumps({case.id: case.model_dump()}), encoding="utf-8")
    loaded = load_case("legacy-1")
    assert loaded is not None and loaded.plan.next_single_action
    save_case(loaded)                                      # migrates in place
    assert json.loads(temp_db.read_text(encoding="utf-8"))["version"] == 2
    assert load_case("legacy-1").model_dump() == loaded.model_dump()


# ------------------------------------------------------------ 3. listing + reset

def test_list_cases_reports_where_each_case_stands():
    save_case(_fresh_case("case-a"))
    save_case(_fresh_case("case-b"))
    rows = {r["id"]: r for r in list_cases()}
    assert set(rows) == {"case-a", "case-b"}
    row = rows["case-a"]
    assert row["item_count"] == 5
    assert "record-correction" in row["next_single_action"]
    assert row["created"] and row["refusal_count"] == 1 and row["correction_count"] == 0


def test_reset_returns_the_case_to_as_loaded_state():
    case = _fresh_case("case-reset")
    save_case(case)                                        # baseline captured here
    baseline_plan = case.plan.model_dump()

    case.done_keys = ["record_name_matches_id"]
    case, _, _ = apply_correction(case, RECORD_DOC, "owner_name", "WRONG NAME")
    case.plan = build_plan(case)
    save_case(case)
    assert _states(case)["O1"].state == "done"

    restored = reset_case("case-reset")
    assert restored.done_keys == [] and restored.corrections == []
    assert restored.plan.model_dump() == baseline_plan
    owner = next(f for f in restored.drafts[0].identity_fields if f.name == "owner_name")
    assert owner.value == "Sushila D."
    assert load_case("case-reset").plan.model_dump() == baseline_plan   # persisted
    assert case_meta("case-reset")["correction_log"] == []
    assert reset_case("no-such-case") is None


# ------------------------------------------------------------------- 4. HTTP API

def test_api_correct_reload_list_reset_round_trip():
    from fastapi.testclient import TestClient

    from src.app import app
    client = TestClient(app)

    case = client.post("/api/case/fixture/demo").json()
    cid = case["id"]

    body = {"doc_id": RECORD_DOC, "field_name": "owner_name", "new": "SUSHILA DEVI"}
    out = client.post(f"/api/case/{cid}/correct", json=body).json()
    assert out["plan"]["mismatches"] == []
    assert out["last_correction"]["propagated_to"] == out["diff"]["propagated_to"]
    assert "O2" in out["diff"]["propagated_to"]
    # web/index.html reads c.corrections[-1].propagated_to — keep that shape
    assert out["corrections"][-1]["propagated_to"] == out["diff"]["propagated_to"]

    # GET after the write serves the corrected state from disk
    got = client.get(f"/api/case/{cid}").json()
    assert got["plan"] == out["plan"]
    assert got["correction_log"][0]["diff"]["summary"] == out["diff"]["summary"]
    assert got["created"] and got["updated"]

    # a mistyped target is refused with the menu, and changes nothing
    bad = client.post(f"/api/case/{cid}/correct",
                      json={"doc_id": "nope", "field_name": "owner_name", "new": "X"})
    assert bad.status_code == 404 and bad.json()["detail"]["available_targets"]
    assert client.get(f"/api/case/{cid}").json()["corrections"] == got["corrections"]

    listed = {r["id"]: r for r in client.get("/api/cases").json()}
    assert cid in listed and listed[cid]["correction_count"] == 1

    reset_out = client.post(f"/api/case/{cid}/reset").json()
    assert reset_out["corrections"] == [] and reset_out["plan"]["mismatches"]
    assert client.get(f"/api/case/{cid}").json()["plan"] == reset_out["plan"]

    assert client.get("/api/case/ghost").status_code == 404
    assert client.post("/api/case/ghost/reset").status_code == 404
    assert client.post(f"/api/case/{cid}/correct", json={"doc_id": "x"}).status_code == 422
