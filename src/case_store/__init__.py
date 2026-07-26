"""Case persistence + correction propagation — Memory L4 evidence lives here.

Public surface (src/app.py and other branches import from here only):

    load_case(case_id) -> Case | None      # FROZEN signature
    save_case(case) -> None                # FROZEN signature
    list_cases() -> list[dict]             # id, created, item_count, next_single_action
    reset_case(case_id) -> Case | None     # back to as-loaded state (repeat demos)
    case_meta(case_id) -> dict             # created/updated/correction_log sidecar
    log_correction(case_id, entry) -> None
    apply_correction(case, doc_id, field_name, new) -> (case, Correction, diff)
    correction_targets(case) -> list[dict]
    CorrectionTargetNotFound

Storage is a JSON file (see store.py); SQLite stays in the parking lot
(IDEA_SCOPE.md §13) — the rubric asks for governed continuity, not a database.
"""
from __future__ import annotations

from .corrections import (CorrectionTargetNotFound, apply_correction,
                          correction_targets, diff_plans)
from .store import (CaseStore, CaseStoreError, case_meta, list_cases,
                    load_case, log_correction, reset_case, save_case)

__all__ = [
    "CaseStore", "CaseStoreError", "CorrectionTargetNotFound", "apply_correction",
    "case_meta", "correction_targets", "diff_plans", "list_cases", "load_case",
    "log_correction", "reset_case", "save_case",
]
