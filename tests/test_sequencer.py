"""Acceptance tests for the sequencing engine. Run: python -m pytest -q
These pass WITHOUT any Sarvam key — pure logic on the demo fixture."""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.contracts import Case
from src.sequencer.core import build_plan

FIXTURE = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "case_demo.json"


def _load() -> Case:
    return Case.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))


def test_initial_plan():
    plan = build_plan(_load())
    states = {i.obligation_id: i for i in plan.items}

    # O1 actionable and THE next single action
    assert states["O1"].state == "actionable" and states["O1"].order == 1
    assert plan.next_single_action and "record-correction" in plan.next_single_action

    # O2 blocked by O1 with a quotable reason
    assert states["O2"].state == "blocked"
    e = next(x for x in plan.edges if x.blocked_id == "O2" and x.blocker_id == "O1")
    assert "must match record-of-rights" in e.reason
    assert len(e.evidence) >= 2  # the requirement quote + both mismatch readings

    # O3 blocked by O2 (chain), O4 duplicate of O3, O5 unknown
    assert any(x.blocked_id == "O3" and x.blocker_id == "O2" for x in plan.edges)
    assert states["O4"].state == "duplicate" and states["O4"].duplicate_of == "O3"
    assert states["O5"].state == "unknown"

    # refusal: plot_area at 0.55 < 0.75 refused, never guessed
    assert any(r.name == "plot_area" and r.status == "refused" for r in plan.refusals)

    # mismatch: 'Sushila D.' vs 'SUSHILA DEVI' classified cosmetic (card 17)
    m = next(m for m in plan.mismatches if m.field_name == "owner_name")
    assert m.classification == "cosmetic"


def test_resequence_after_blocker_done():
    case = _load()
    case.done_keys = ["record_name_matches_id"]
    plan = build_plan(case)
    states = {i.obligation_id: i for i in plan.items}
    assert states["O1"].state == "done"
    assert states["O2"].state == "actionable" and states["O2"].order == 1
    assert plan.next_single_action and "mutation application" in plan.next_single_action.lower()
