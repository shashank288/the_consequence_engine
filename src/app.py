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

from .case_store import load_case, save_case
from .contracts import Case, Correction
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
    case.plan = build_plan(case)
    save_case(case)
    return case.model_dump()


@app.post("/api/case")
async def create_from_uploads(files: list[UploadFile]):
    # feat/extraction owns this: Doc-Intelligence job -> ObligationDrafts -> plan
    raise HTTPException(501, "extraction pipeline lands via feat/extraction; use fixture mode")


@app.get("/api/case/{case_id}")
def get_case(case_id: str):
    case = load_case(case_id)
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
    case.plan = build_plan(case)
    save_case(case)
    return case.model_dump()


@app.post("/api/case/{case_id}/correct")
def correct(case_id: str, body: dict):
    """Correction propagation (Memory L4): patch one field reading, rebuild, record."""
    case = load_case(case_id)
    if case is None:
        raise HTTPException(404, "no such case")
    doc_id, field, new = body.get("doc_id"), body.get("field_name"), body.get("new")
    if not (doc_id and field and new):
        raise HTTPException(422, "doc_id, field_name, new required")
    old, touched = None, []
    for d in case.drafts:
        for f in [d.due, d.amount, *d.identity_fields]:
            if f and f.name == field and f.source and f.source.doc_id == doc_id:
                old, f.value, f.status, f.confidence = f.value, new, "read", 1.0
                touched.append(d.id)
    case.plan = build_plan(case)
    touched += [e.blocked_id for e in case.plan.edges if any(
        s.doc_id == doc_id for s in e.evidence)]
    case.corrections.append(Correction(doc_id=doc_id, field_name=field, old=old,
                                       new=new, propagated_to=sorted(set(touched))))
    save_case(case)
    return case.model_dump()


app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
