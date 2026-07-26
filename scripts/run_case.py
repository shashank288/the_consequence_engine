"""CLI golden path: python -m scripts.run_case [fixture-name]"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from src.contracts import Case
from src.sequencer.core import build_plan

name = sys.argv[1] if len(sys.argv) > 1 else "demo"
fx = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / f"case_{name}.json"
case = Case.model_validate(json.loads(fx.read_text(encoding="utf-8")))
plan = build_plan(case)
print(f"NEXT SINGLE ACTION: {plan.next_single_action}\n")
for i in sorted(plan.items, key=lambda x: (x.order or 99)):
    print(f"  [{i.state:>10}] {i.obligation_id}"
          + (f" (dup of {i.duplicate_of})" if i.duplicate_of else ""))
print("\nEDGES:")
for e in plan.edges:
    print(f"  {e.blocked_id} ⇐ blocked by {e.blocker_id}: {e.reason}")
print("\nREFUSALS:", [r.name for r in plan.refusals])
print("MISMATCHES:", [(m.field_name, m.classification) for m in plan.mismatches])
