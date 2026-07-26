"""Case persistence — Memory L4 evidence lives here.

Lite JSON-file store on main so the golden path runs immediately.
feat/case-memory may upgrade to SQLite + richer history WITHOUT changing
these two function signatures (the app depends only on them).
"""
from __future__ import annotations

import json
import pathlib

from ..config import CASE_DB
from ..contracts import Case

_PATH = pathlib.Path(CASE_DB)


def _read_all() -> dict:
    if _PATH.exists():
        return json.loads(_PATH.read_text(encoding="utf-8"))
    return {}


def save_case(case: Case) -> None:
    data = _read_all()
    data[case.id] = case.model_dump()
    _PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def load_case(case_id: str) -> Case | None:
    data = _read_all()
    if case_id in data:
        return Case.model_validate(data[case_id])
    return None
