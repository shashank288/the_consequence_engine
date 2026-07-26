"""feat/register — card 87: the decades-old handwritten mutation-register page.

Three things live here, in the order the demo shows them:

  1. `policy.apply_register_policy` — a stricter, stated refusal bar for
     handwritten register pages, plus the move that earns the Document
     Intelligence score: a reading is refused when the PIXELS UNDER IT are
     obstructed, however confident the model was.
  2. `crops.crop_field` — the escalation panel shows the cropped cell, not the
     whole page. A judge looks at the crop and agrees it is unreadable.
  3. `contradictions.check_contradictions` — this page versus the last accepted
     entry in the mocked records system, flagged with a plain-language reason.

`reader.py` is what makes (1) and (2) possible without a model: it registers the
ruled form onto the photograph and finds the seal and correction ink. It reads
no text and invents no values.

Entry point for callers: `build_plan_with_register(case)` — policy, plan,
contradictions, in that order.

Acceptance: a held-out handwritten page produces >=1 refused field routed with
its crop, and 1 contradiction flagged against the mocked prior record.
"""
from __future__ import annotations

from ..contracts import Case, Plan
from ..sequencer.core import build_plan
from .contradictions import check_contradictions
from .crops import CropUnavailable, crop_field
from .policy import (REGISTER_DOC_TYPES, REGISTER_REFUSE_BELOW,
                     apply_register_policy, is_register, resolve_pages)
from .reader import Cell, Defect, PageAudit, audit_page, find_defects
from .records import PRIOR_RECORDS, prior_record

__all__ = [
    "PRIOR_RECORDS", "prior_record", "crop_field", "CropUnavailable",
    "apply_register_policy", "check_contradictions", "audit_page", "find_defects",
    "PageAudit", "Cell", "Defect", "is_register", "resolve_pages",
    "REGISTER_DOC_TYPES", "REGISTER_REFUSE_BELOW", "build_plan_with_register",
]

_SUPERSEDED = "superseded reading on the page"


def _strip_refused_values(plan: Plan) -> None:
    """A refused field must not travel with a value.

    The sequencer already nulls sub-threshold readings; a reading refused on
    PAGE evidence can be above threshold, so it arrives here still carrying its
    text. The text is kept — as an explicitly superseded quote on the source, so
    the escalation view can show what was written — but the value field, which
    downstream code treats as usable, is emptied.
    """
    for r in plan.refusals:
        if r.value is None:
            continue
        quote = (r.source.quote or "") if r.source is not None else ""
        if r.source is not None and _SUPERSEDED not in quote and r.value not in quote:
            r.source.quote = (f"{quote}{' · ' if quote else ''}"
                              f"{_SUPERSEDED}: '{r.value}'")
        r.value = None


def _new_contradictions(plan: Plan, found) -> list:
    """Drop anything the sequencer's own mismatch pass already reports."""
    seen = {(m.field_name, tuple(sorted((r.value or "") for r in m.readings)))
            for m in plan.mismatches}
    out = []
    for m in found:
        key = (m.field_name, tuple(sorted((r.value or "") for r in m.readings)))
        if key not in seen:
            seen.add(key)
            out.append(m)
    return out


def build_plan_with_register(case: Case, pages: dict[str, str] | None = None) -> Plan:
    """`build_plan`, with the register page's own evidence folded in.

    Order matters: the policy runs BEFORE the sequencer so refusals reach the
    plan through the existing machinery, and the contradiction pass runs after
    so it can see what the policy refused. Idempotent, and a no-op for a case
    that holds no register page — the packaged fixture demo keeps behaving
    exactly as `build_plan` alone.

    `pages` maps doc_id -> page image path; without it, images are looked up by
    doc_id under fixtures/private/ (see `policy.resolve_pages`).
    """
    apply_register_policy(case.drafts, pages=pages)
    plan = build_plan(case)
    _strip_refused_values(plan)
    plan.mismatches = plan.mismatches + _new_contradictions(
        plan, check_contradictions(case.drafts))
    return plan
