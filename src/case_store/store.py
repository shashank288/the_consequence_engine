"""Case persistence — the Memory L4 substrate.

One JSON file, one envelope per case:

    {"version": 2,
     "cases": {"<case_id>": {"case":     {...Case...},
                             "meta":     {"created", "updated", "correction_log": [...]},
                             "baseline": {...Case as first saved...}}}}

Two things the envelope buys us that a bare `{id: case}` map cannot:

* `baseline` — what `reset_case` restores, so the demo can be run repeatedly (M5).
* `meta` — continuity the FROZEN Case contract has no field for (timestamps,
  propagation diffs) WITHOUT touching src/contracts.py.

Every read hits the file, so a fresh store instance in a fresh process resumes
the persisted state — that is the reload-resume proof.

`load_case(case_id)` / `save_case(case)` signatures are load-bearing for
src/app.py and other branches. Everything else here is additive.
"""
from __future__ import annotations

import copy
import json
import os
import pathlib
from datetime import datetime, timezone

from ..config import CASE_DB
from ..contracts import Case
from ..sequencer.core import build_plan

SCHEMA_VERSION = 2
_REPO = pathlib.Path(__file__).resolve().parents[2]


class CaseStoreError(RuntimeError):
    """The store file exists but is not readable as a case database."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _default_path() -> pathlib.Path:
    """CASE_DB, resolved at call time (tests point it at tmp_path) and anchored
    to the repo so the demo resumes the same file whatever the cwd is."""
    p = pathlib.Path(os.getenv("CASE_DB") or CASE_DB).expanduser()
    return p if p.is_absolute() else _REPO / p


def _empty() -> dict:
    return {"version": SCHEMA_VERSION, "cases": {}}


def _envelope(dump: dict) -> dict:
    return {"case": dump,
            "meta": {"created": _now(), "updated": _now(), "correction_log": []},
            "baseline": copy.deepcopy(dump)}


class CaseStore:
    """Disk-backed case store. Stateless between calls on purpose."""

    def __init__(self, path: str | os.PathLike | None = None) -> None:
        self.path = pathlib.Path(path) if path is not None else _default_path()

    # ---------------------------------------------------------------- file I/O
    def _read(self) -> dict:
        if not self.path.exists():
            return _empty()
        text = self.path.read_text(encoding="utf-8").strip()
        if not text:
            return _empty()
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:      # never silently overwrite data
            raise CaseStoreError(
                f"{self.path} is not valid JSON ({exc}); move it aside to start fresh") from exc
        if not isinstance(raw, dict):
            raise CaseStoreError(f"{self.path} does not hold a case database")
        if isinstance(raw.get("cases"), dict):
            return {"version": raw.get("version", SCHEMA_VERSION), "cases": raw["cases"]}
        # legacy flat {case_id: case_dump} written by the lite store on main
        return {"version": SCHEMA_VERSION,
                "cases": {cid: _envelope(dump) for cid, dump in raw.items()
                          if isinstance(dump, dict)}}

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(f"{self.path.name}.tmp{os.getpid()}")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.path)               # atomic: no half-written case DB

    # ---------------------------------------------------------------- public
    def save(self, case: Case) -> None:
        data = self._read()
        dump = case.model_dump()
        env = data["cases"].get(case.id)
        if env is None:
            data["cases"][case.id] = _envelope(dump)
        else:
            env["case"] = dump
            meta = env.setdefault("meta", {})
            meta.setdefault("created", _now())
            meta.setdefault("correction_log", [])
            meta["updated"] = _now()
            env.setdefault("baseline", copy.deepcopy(dump))
        self._write(data)

    def load(self, case_id: str) -> Case | None:
        env = self._read()["cases"].get(case_id)
        return Case.model_validate(env["case"]) if env else None

    def meta(self, case_id: str) -> dict:
        env = self._read()["cases"].get(case_id)
        return copy.deepcopy(env.get("meta", {})) if env else {}

    def log_correction(self, case_id: str, entry: dict) -> None:
        """Persist a correction + its propagation diff beside the case, so the
        handoff after a reload is a concise state and not a re-derivation."""
        data = self._read()
        env = data["cases"].get(case_id)
        if env is None:
            return
        env.setdefault("meta", {}).setdefault("correction_log", []).append({"at": _now(), **entry})
        self._write(data)

    def list(self) -> list[dict]:
        rows = []
        for cid, env in self._read()["cases"].items():
            case, meta = env.get("case", {}), env.get("meta", {})
            plan = case.get("plan") or {}
            rows.append({
                "id": cid,
                "created": meta.get("created"),
                "updated": meta.get("updated"),
                "item_count": len(plan.get("items") or case.get("drafts") or []),
                "next_single_action": plan.get("next_single_action"),
                "refusal_count": len(plan.get("refusals") or []),
                "correction_count": len(case.get("corrections") or []),
            })
        rows.sort(key=lambda r: (r["created"] or "", r["id"]))
        return rows

    def reset(self, case_id: str) -> Case | None:
        """Back to as-loaded state (first save), plan re-derived from the drafts."""
        data = self._read()
        env = data["cases"].get(case_id)
        if env is None:
            return None
        case = Case.model_validate(copy.deepcopy(env.get("baseline") or env["case"]))
        case.plan = build_plan(case)
        env["case"] = case.model_dump()
        meta = env.setdefault("meta", {})
        meta["updated"] = _now()
        meta["correction_log"] = []
        meta["reset_count"] = meta.get("reset_count", 0) + 1
        self._write(data)
        return case


# ------------------------------------------------------------------ module API
# A fresh store per call: always disk truth, and CASE_DB stays overridable.

def save_case(case: Case) -> None:
    CaseStore().save(case)


def load_case(case_id: str) -> Case | None:
    return CaseStore().load(case_id)


def list_cases() -> list[dict]:
    return CaseStore().list()


def reset_case(case_id: str) -> Case | None:
    return CaseStore().reset(case_id)


def case_meta(case_id: str) -> dict:
    return CaseStore().meta(case_id)


def log_correction(case_id: str, entry: dict) -> None:
    CaseStore().log_correction(case_id, entry)
