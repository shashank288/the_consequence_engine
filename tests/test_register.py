"""feat/register acceptance tests (M3). Run: py -3.12 -m pytest -q

No Sarvam key, no network: everything here is local work on an image plus pure
logic. The headline test is `test_holdout_page_...` — the agent brief's
acceptance criterion, run against the page held out of the build:

    a held-out handwritten page produces >=1 refused field routed with its
    cropped image, and 1 contradiction flagged against the mocked prior record.

The page images live under fixtures/private/ (git-ignored, privacy hygiene) and
are regenerated deterministically from scripts/make_register_page.py. Tests that
need one generate it on demand and skip if that is not possible.
"""
import json
import pathlib
import subprocess
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.contracts import Case, FieldReading, ObligationDraft, SourceRef
from src.register import (REGISTER_REFUSE_BELOW, apply_register_policy,
                          audit_page, build_plan_with_register,
                          check_contradictions, crop_field, prior_record)
from src.register.crops import CropUnavailable
from src.register.reader import base_name, draft_from_page, qualified_name
from src.sequencer.core import build_plan

ROOT = pathlib.Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures" / "private"
DEMO_FIXTURE = ROOT / "fixtures" / "case_demo.json"

# seed -> file, per docs/DATASET.md. 13 is the page held out of the build.
PAGES = {"register_page": 42, "register_holdout": 13}

# What the extractor would hand us for the first three rows of the form. Values
# only — every bbox, every obstruction and therefore every refusal below is
# measured from the image. 0.91 on the sealed cell is deliberately above every
# threshold in the system: the point is that page evidence overrules it.
ROWS = [
    {"row": 1, "survey_no": ("SN-143", 0.94), "owner_name": ("सुशीला देवी", 0.79),
     "area": ("१ एकड़ ०५ गुंठा", 0.91)},
    {"row": 0, "survey_no": ("SN-142/2", 0.92), "owner_name": ("रामय्या स.", 0.88),
     "area": ("२ एकड़ १३ गुंठा", 0.87)},
    {"row": 2, "survey_no": ("SN-144/1", 0.90), "owner_name": ("लक्ष्मम्मा", 0.86),
     "area": ("३ एकड़ ०० गुंठा", 0.91)},
]


def page(name: str = "register_holdout") -> str:
    """Path to a demo page, generated on demand. Skips if it cannot be made."""
    out = PRIVATE / f"{name}.png"
    if not out.exists():
        try:
            subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "make_register_page.py"),
                 "--seed", str(PAGES[name]), "--out", str(out)],
                check=True, capture_output=True, cwd=ROOT, timeout=120)
        except (OSError, subprocess.SubprocessError):
            pytest.skip(f"cannot generate {out} (Devanagari font unavailable?)")
    if not out.exists():
        pytest.skip(f"{out} unavailable")
    return str(out)


def register_case(name: str = "register_holdout", rows=None) -> tuple[Case, str]:
    img = page(name)
    draft = draft_from_page(img, name, rows or ROWS)
    return Case(id=f"case-{name}", drafts=[draft]), img


def refusal(plan, field: str):
    return next((r for r in plan.refusals if r.name == field), None)


# ----------------------------------------------------------- 1. THE ACCEPTANCE

def test_holdout_page_refuses_with_a_crop_and_contradicts_the_prior_record():
    """M3, on a page never opened during the build."""
    case, img = register_case()
    plan = build_plan_with_register(case, pages={"register_holdout": img})

    routed = [r for r in plan.refusals if r.source and r.source.crop_path]
    assert routed, "no refused field carried a crop"

    for r in routed:
        assert r.status == "refused"
        assert r.value is None, "a refused field must not travel with a value"
        crop = ROOT / "web" / r.source.crop_path
        assert crop.exists() and crop.stat().st_size > 0
        assert r.source.crop_path.startswith("crops/")     # servable by src/app.py
        assert "REFUSED (" in (r.source.quote or ""), "the refusal must state why"

    contradictions = [m for m in plan.mismatches
                      if any((s.source.doc_id if s.source else "").startswith("prior_record:")
                             for s in m.readings)]
    assert contradictions, "no contradiction raised against the records system"
    blocking = [m for m in contradictions if m.classification == "blocking"]
    assert blocking, "the struck-through owner must block, not pass quietly"
    assert "SN-143" in blocking[0].reason and "Sushila Devi" in blocking[0].reason


def test_holdout_page_is_registered_and_its_obstructions_found():
    audit = audit_page(page())
    assert audit.registered, "the ruled form was not located on the photograph"
    kinds = {d.kind for d in audit.defects}
    assert {"seal", "strike"} <= kinds, f"expected seal and strike, got {kinds}"
    # the seal sits over the area column, on the right-hand half of the page
    seal = max((d for d in audit.defects if d.kind == "seal"), key=lambda d: d.tiles)
    assert seal.bbox[0] > 0.5 and seal.bbox[2] > seal.bbox[0]


# ------------------------------------------------- 2. evidence beats confidence

def test_page_evidence_overrules_a_confident_reading():
    """The L4->L5 move: 0.91 is above every threshold we have, and the seal
    still wins, because the pixels under the value are covered."""
    case, img = register_case()
    plan = build_plan_with_register(case, pages={"register_holdout": img})

    sealed = refusal(plan, qualified_name("area", "SN-144/1"))
    assert sealed is not None, "the sealed area cell was not refused"
    assert sealed.confidence > REGISTER_REFUSE_BELOW    # not a threshold refusal
    assert "occluded_by_seal" in sealed.source.quote
    assert sealed.source.crop_path


def test_a_clean_cell_on_the_same_page_is_left_alone():
    """Refusing everything would be as useless as guessing. The unobstructed
    first row stays read, and never acquires a crop or a refusal note."""
    case, img = register_case()
    build_plan_with_register(case, pages={"register_holdout": img})

    clean = {f.name: f for f in case.drafts[0].identity_fields}
    for name in (qualified_name("owner_name", "SN-142/2"),
                 qualified_name("area", "SN-142/2")):
        assert clean[name].status == "read"
        assert clean[name].value
        assert "REFUSED" not in (clean[name].source.quote or "")


def test_struck_through_owner_is_refused_not_silently_resolved():
    """docs/DATASET.md: 'Which is current? The system must not silently pick one.'"""
    case, img = register_case()
    build_plan_with_register(case, pages={"register_holdout": img})
    owner = next(f for f in case.drafts[0].identity_fields if f.name == "owner_name")
    assert owner.status == "refused" and "overwritten" in owner.source.quote


# ------------------------------------------------------------- 3. crop plumbing

def test_crop_field_writes_a_servable_image_deterministically(tmp_path):
    img = page("register_page")
    bbox = [0.30, 0.18, 0.52, 0.22]
    first = crop_field(img, bbox, out_dir=str(tmp_path), name="owner_name")
    again = crop_field(img, bbox, out_dir=str(tmp_path), name="owner_name")
    assert first == again, "the same field must not accumulate crops on re-run"
    assert first.startswith("crops/") and first.endswith(".png")

    from PIL import Image
    written = tmp_path / pathlib.Path(first).name
    assert written.exists()
    with Image.open(written) as crop, Image.open(img) as whole:
        assert crop.size[0] < whole.size[0], "the crop must be a cell, not the page"
        assert crop.size[0] > 20 and crop.size[1] > 10


def test_crop_field_refuses_rather_than_returning_a_broken_path(tmp_path):
    img = page("register_page")
    with pytest.raises(CropUnavailable):
        crop_field(img, [0.4, 0.4, 0.4, 0.4], out_dir=str(tmp_path))
    with pytest.raises(CropUnavailable):
        crop_field(str(tmp_path / "nope.png"), [0.1, 0.1, 0.2, 0.2], out_dir=str(tmp_path))
    with pytest.raises(CropUnavailable):
        crop_field(img, [0.1, 0.1], out_dir=str(tmp_path))


# ------------------------------------------------------------------- 4. policy

def _draft(**reading) -> ObligationDraft:
    fields = [FieldReading(name=n, value=v, confidence=c, status="read",
                           source=SourceRef(doc_id="p1", quote=q))
              for n, (v, c, q) in reading.items()]
    return ObligationDraft(id="O1", doc_id="p1", doc_type="mutation_register_page",
                           asked_what="correct the record", asked_by="Tehsil office",
                           identity_fields=fields)


def test_stricter_bar_applies_only_where_we_have_looked_at_the_page():
    """The stricter bar is a claim about the page, so it needs the page. Without
    one the global bar governs — which is what keeps this branch off the backs of
    cases assembled from fixtures alone."""
    without = _draft(owner_name=("Sushila D.", 0.80, "मालिक — Sushila D."))
    apply_register_policy([without])
    assert without.identity_fields[0].status == "read"          # 0.80 > global 0.75

    img = page("register_page")
    with_page = _draft(owner_name=("Sushila D.", 0.80, "मालिक — Sushila D."))
    with_page.doc_id = "register_page"
    for f in with_page.identity_fields:
        f.source.doc_id = "register_page"
    apply_register_policy([with_page], pages={"register_page": img})
    assert with_page.identity_fields[0].status == "refused"     # 0.80 < 0.85
    assert "low_confidence" in with_page.identity_fields[0].source.quote


def test_an_extractor_hint_refuses_without_any_image():
    """Page evidence we did not measure ourselves is still page evidence."""
    draft = _draft(area=("2 acre 13 gunta", 0.97,
                         "(overwritten, seal partially covering)"))
    apply_register_policy([draft])
    field = draft.identity_fields[0]
    assert field.status == "refused" and "occluded_by_seal" in field.source.quote


def test_policy_does_not_touch_other_doc_types():
    draft = _draft(owner_name=("Sushila D.", 0.10, "x"))
    draft.doc_type = "bank_letter"
    apply_register_policy([draft])
    assert draft.identity_fields[0].status == "read"


def test_policy_is_idempotent():
    case, img = register_case()
    apply_register_policy(case.drafts, pages={"register_holdout": img})
    once = [f.model_dump() for f in case.drafts[0].identity_fields]
    apply_register_policy(case.drafts, pages={"register_holdout": img})
    assert [f.model_dump() for f in case.drafts[0].identity_fields] == once


def test_qualified_names_keep_other_rows_out_of_this_obligations_identity():
    """A register page lists several plots; two plain `owner_name` readings on
    one obligation would read to the sequencer as one person named twice."""
    case, img = register_case()
    names = [f.name for f in case.drafts[0].identity_fields]
    assert names.count("owner_name") == 1
    assert qualified_name("owner_name", "SN-142/2") in names
    assert base_name(qualified_name("area", "SN-144/1")) == "area"

    plan = build_plan_with_register(case, pages={"register_holdout": img})
    invented = [m for m in plan.mismatches
                if not any((r.source.doc_id if r.source else "").startswith("prior_record:")
                           for r in m.readings)]
    assert invented == [], f"the page's own rows were cross-compared: {invented}"


# ---------------------------------------------------------- 5. contradictions

def test_no_flag_when_the_two_scripts_provably_agree():
    """लक्ष्मम्मा vs 'Lakshmamma' is the same name. A system that flags it
    trains its user to ignore the panel."""
    case, img = register_case()
    build_plan_with_register(case, pages={"register_holdout": img})
    flagged = {m.reason for m in check_contradictions(case.drafts)}
    assert not any("SN-144/1" in r for r in flagged), flagged


def test_unconfirmable_transliteration_is_unknown_not_blocking():
    case, _ = register_case()
    found = [m for m in check_contradictions(case.drafts) if "SN-142/2" in m.reason]
    assert len(found) == 1 and found[0].classification == "unknown"
    assert "cannot confirm" in found[0].reason


def test_owner_is_paired_with_its_own_plot_row():
    case, img = register_case()
    build_plan_with_register(case, pages={"register_holdout": img})
    for m in check_contradictions(case.drafts):
        plot = next(r for r in m.readings
                    if (r.source.doc_id or "").startswith("prior_record:"))
        assert prior_record(plot.source.doc_id.split(":", 1)[1])["owner_name"] == plot.value


def test_prior_record_lookup_is_exact_never_fuzzy():
    assert prior_record("SN-142/2")["owner_name"] == "Ramaiah S."
    assert prior_record(" sn-142/2 ") is not None          # whitespace/case only
    assert prior_record("SN-142") is None                  # a half-read number is not a match
    assert prior_record("") is None and prior_record(None) is None


def test_contradiction_needs_a_plot_it_can_name():
    """No plot number on the page means no lookup — never a guessed record."""
    draft = _draft(owner_name=("सुशीला बाई", 0.9, "सुशीला बाई"))
    assert check_contradictions([draft]) == []


# ------------------------------------------------- 6. the fixture golden path

def test_fixture_demo_plan_is_unchanged_by_this_branch():
    """POST /api/case/fixture/demo must NEVER break (CLAUDE.md rule 3). The
    fixture carries no page image, so the register hook adds no item, edge,
    mismatch or refusal — it only states WHY the already-refused field was
    refused."""
    raw = json.loads(DEMO_FIXTURE.read_text(encoding="utf-8"))
    before = build_plan(Case.model_validate(raw))
    after = build_plan_with_register(Case.model_validate(raw))

    assert [i.model_dump() for i in after.items] == [i.model_dump() for i in before.items]
    assert [e.model_dump() for e in after.edges] == [e.model_dump() for e in before.edges]
    assert ([m.model_dump() for m in after.mismatches]
            == [m.model_dump() for m in before.mismatches])
    assert [r.name for r in after.refusals] == [r.name for r in before.refusals] == ["plot_area"]
    assert after.next_single_action == before.next_single_action
    assert "REFUSED (occluded_by_seal)" in after.refusals[0].source.quote


def test_api_fixture_route_still_serves_a_plan():
    from fastapi.testclient import TestClient

    from src.app import app
    body = TestClient(app).post("/api/case/fixture/demo").json()
    assert body["plan"]["next_single_action"]
    assert [r["name"] for r in body["plan"]["refusals"]] == ["plot_area"]
    assert body["plan"]["mismatches"], "the owner_name mismatch is a demo beat"
