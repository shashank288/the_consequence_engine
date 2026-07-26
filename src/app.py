"""FastAPI app — serves web/ and the case API.

Run:  uvicorn src.app:app --reload --port 8000
Golden path works TODAY with zero Sarvam key via fixture mode:
POST /api/case/fixture/demo  → plan renders in web UI.
feat/extraction replaces the 501 in POST /api/case with the real pipeline.
"""
from __future__ import annotations

import json
import pathlib
import uuid

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .case_store import (CorrectionTargetNotFound, apply_correction, case_meta,
                         correction_targets, list_cases, load_case, log_correction,
                         reset_case, save_case)
from .contracts import Case
from .register import build_plan_with_register
from .sequencer.core import build_plan

ROOT = pathlib.Path(__file__).resolve().parents[1]
app = FastAPI(title="The Consequence Engine")


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/case/fixture/{name}")
def create_from_fixture(name: str):
    path = ROOT / "fixtures" / f"case_{name}.json"
    if not path.exists():
        raise HTTPException(404, f"fixture {name} not found")
    case = Case.model_validate(json.loads(path.read_text(encoding="utf-8")))
    case.id = f"{case.id}-{uuid.uuid4().hex[:6]}"
    case.plan = build_plan_with_register(case)
    save_case(case)
    return case.model_dump()


@app.post("/api/case")
async def create_from_uploads(files: list[UploadFile]):
    # feat/extraction owns this: Doc-Intelligence job -> ObligationDrafts -> plan
    raise HTTPException(501, "extraction pipeline lands via feat/extraction; use fixture mode")


@app.get("/api/cases")
def list_all_cases():
    """Demo hygiene: which cases exist on disk and where each one stands."""
    return list_cases()


@app.get("/api/case/{case_id}")
def get_case(case_id: str):
    """Reload-resume (Memory L4): read from disk every call, so a fresh process
    serves the identical plan. `correction_log` carries the propagation history
    the FROZEN Case contract has no field for."""
    case = load_case(case_id)
    if case is None:
        raise HTTPException(404, "no such case")
    meta = case_meta(case_id)
    return {**case.model_dump(),
            "created": meta.get("created"),
            "updated": meta.get("updated"),
            "correction_log": meta.get("correction_log", [])}


@app.post("/api/case/{case_id}/reset")
def reset(case_id: str):
    """Back to as-loaded state so the demo can be run repeatedly (M5)."""
    case = reset_case(case_id)
    if case is None:
        raise HTTPException(404, "no such case")
    return case.model_dump()


@app.post("/api/case/{case_id}/status/{key}")
def mark_done(case_id: str, key: str):
    """Mock status lookup: an obligation's provided key is now satisfied upstream."""
    case = load_case(case_id)
    if case is None:
        raise HTTPException(404, "no such case")
    if key not in case.done_keys:
        case.done_keys.append(key)
    # register-aware: keeps page-evidence refusals and prior-record contradictions
    # in the plan after a status lookup. No-op for cases with no register page.
    case.plan = build_plan_with_register(case)
    save_case(case)
    return case.model_dump()


@app.post("/api/case/{case_id}/correct")
def correct(case_id: str, body: dict):
    """Correction propagation (Memory L4).

    Patches EVERY reading of (doc_id, field_name), re-derives the plan, and
    returns the before/after diff — `propagated_to` names the obligations whose
    state, mismatch, blocking edge or refusal actually changed. Unknown targets
    are refused with the available ones, never recorded as a silent no-op.
    """
    case = load_case(case_id)
    if case is None:
        raise HTTPException(404, "no such case")
    doc_id, field, new = body.get("doc_id"), body.get("field_name"), body.get("new")
    if not (doc_id and field and new):
        raise HTTPException(422, "doc_id, field_name, new required")
    try:
        case, correction, diff = apply_correction(case, doc_id, field, new)
    except CorrectionTargetNotFound as exc:
        raise HTTPException(404, {"error": str(exc),
                                  "available_targets": exc.available}) from exc
    save_case(case)
    log_correction(case_id, {"correction": correction.model_dump(), "diff": diff})
    return {**case.model_dump(), "last_correction": correction.model_dump(), "diff": diff}


app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
