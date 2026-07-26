"""Handwriting-aware refusal policy for the mutation-register page.

The global bar in config.py (`REFUSE_BELOW = 0.75`) is calibrated for printed
paper. A decades-old handwritten register is a different instrument: mixed
hands, mixed scripts, seals, and corrections written over the original. This
module layers a stricter, *stated* bar on top of the global one — it never
loosens it — and adds a second, independent test that confidence alone cannot
do:

    A reading is refused when the PIXELS UNDER IT are obstructed, however
    confident the model was.

That is the point of the branch. An OCR that returns "३ एकड़ ०० गुंठा" at 0.91
for a cell with a tehsil seal across it is confidently wrong; `reader.py` sees
the seal and this module overrules the reading, routes it, and attaches the
crop so a human can judge for themselves.

WHEN THE STRICTER BAR APPLIES — read this before changing it
------------------------------------------------------------
`REGISTER_REFUSE_BELOW` applies to a consequence-bearing reading on a register
page **whose image we hold and have audited**. The stricter bar is a claim
about the page ("this is degraded handwriting; 0.80 here is not 0.80 on a
printed slip"), so we require having actually looked at the page before making
it. A case assembled without the page image keeps the global 0.75 bar — which
also means this branch cannot silently re-refuse readings in the packaged
fixture demo that other branches' acceptance tests depend on. Supply the image
and you get the strict bar; that is the whole rule.

An extraction-supplied hint ("seal partially covering", "overwritten") is
page evidence in its own right and forces a refusal with no image at all.

Nothing here guesses, and nothing here silently drops a field: every refusal
lands in `Plan.refusals` with a stated reason and, where we have the page, a
cropped image of the exact paper it rests on.
"""
from __future__ import annotations

import pathlib

from ..config import REFUSE_BELOW
from ..contracts import FieldReading, ObligationDraft, SourceRef
from .crops import CropUnavailable, crop_field
from .reader import PageAudit, audit_page, base_name

REGISTER_DOC_TYPES = {"mutation_register_page", "record_of_rights", "khatauni"}

# Stricter than config.REFUSE_BELOW (0.75) and deliberately so. Rationale in the
# module docstring; never set this BELOW the global bar — the policy may only
# tighten. Chosen, not tuned: 0.85 is the level at which a Devanagari reading
# off a degraded page has been worth acting on in our own inspection, and it
# leaves a visible band (0.75-0.85) that a printed page would have accepted.
REGISTER_REFUSE_BELOW = 0.85

# The consequence-bearing fields on this doc type (agent brief, Task 2). A wrong
# value in any of these gets a mutation application rejected at the counter.
REGISTER_FIELDS = {"owner_name", "plot_no", "survey_no", "area", "plot_area",
                   "date", "deadline"}

REASONS = {
    "occluded_by_seal": "an office seal is stamped across this cell",
    "overwritten": "the entry is struck through and rewritten — two competing "
                   "values, and the page does not say which is current",
    "low_confidence": "handwriting could not be read to the standard a register "
                      "page requires",
    "multiple_hands": "the cell carries more than one hand",
    "illegible": "the cell is damaged or faded past reading",
}

# Hints an extractor may put in its own quote. Page evidence without the page.
HINTS = [
    (("seal", "stamp", "मुहर", "तहसील"), "occluded_by_seal"),
    (("overwrit", "struck", "strike", "crossed out", "corrected over"), "overwritten"),
    (("multiple hands", "second hand", "different hand"), "multiple_hands"),
    (("illegible", "faded", "torn", "damaged", "unreadable"), "illegible"),
]

_MARK = " — REFUSED ("               # idempotency marker in the annotated quote
_PRIVATE = pathlib.Path(__file__).resolve().parents[2] / "fixtures" / "private"


def is_register(draft: ObligationDraft) -> bool:
    return draft.doc_type in REGISTER_DOC_TYPES


def resolve_pages(drafts, pages: dict[str, str] | None = None) -> dict[str, str]:
    """doc_id -> page image path.

    Explicit mapping wins (feat/extraction knows where it saved the upload).
    Otherwise look for a file named after the doc under fixtures/private/ — the
    convention the demo pages already follow. A doc we cannot find an image for
    simply gets no page evidence; it is never treated as if it had none.
    """
    found = dict(pages or {})
    for d in drafts:
        if d.doc_id in found or not is_register(d):
            continue
        for ext in (".png", ".jpg", ".jpeg", ".webp"):
            cand = _PRIVATE / f"{d.doc_id}{ext}"
            if cand.exists():
                found[d.doc_id] = str(cand)
                break
    return {k: v for k, v in found.items() if pathlib.Path(v).exists()}


def hint_reason(reading: FieldReading) -> str | None:
    """A refusal reason the extractor's own words already justify."""
    quote = ((reading.source.quote if reading.source else "") or "").lower()
    if _MARK.strip() in quote:                      # already annotated by us
        return None
    for needles, reason in HINTS:
        if any(n in quote for n in needles):
            return reason
    return None


def _refuse(reading: FieldReading, doc_id: str, reason: str, detail: str) -> None:
    """Mark refused and STATE WHY on the source, idempotently.

    `value` is deliberately left on the draft: the superseded reading stays
    visible to the correction flow (feat/case-memory reports it as `old`).
    `build_plan_with_register` strips it from the plan so nothing user-facing
    ever shows a value the system refused to trust.
    """
    reading.status = "refused"
    if reading.source is None:
        reading.source = SourceRef(doc_id=doc_id)
    quote = reading.source.quote or ""
    if _MARK not in quote:
        note = f"{_MARK.strip()}{reason}): {detail}"
        reading.source.quote = f"{quote}{' ' if quote else ''}{note}".strip()


def _attach_crop(reading: FieldReading, image_path: str) -> None:
    """Best-effort. A crop that cannot be produced degrades to a quote-only
    refusal (the documented cut order) — the refusal itself never depends on it."""
    src = reading.source
    if src is None or not src.bbox or src.crop_path:
        return
    try:
        src.crop_path = crop_field(image_path, src.bbox, name=reading.name)
    except (CropUnavailable, OSError):
        src.crop_path = None


def apply_register_policy(drafts, pages: dict[str, str] | None = None,
                          audits: dict[str, PageAudit] | None = None):
    """Refuse what a register page cannot support, with a stated reason + crop.

    Mutates and returns `drafts` (the brief's signature). Idempotent: running it
    twice produces the same drafts, so it is safe on a reloaded case.
    """
    drafts = list(drafts)
    page_paths = resolve_pages(drafts, pages)
    audits = dict(audits or {})
    for doc_id, path in page_paths.items():
        if doc_id not in audits:
            try:
                audits[doc_id] = audit_page(path)
            except (FileNotFoundError, OSError, ImportError):
                continue                            # no page evidence; bar stays global

    for d in drafts:
        if not is_register(d):
            continue
        audit = audits.get(d.doc_id)
        image = page_paths.get(d.doc_id)
        for f in [d.due, d.amount, *d.identity_fields]:
            # `area@SN-144/1` is an area reading on another row of the same
            # page: same policy, same crop, no claim on this obligation.
            if f is None or base_name(f.name) not in REGISTER_FIELDS:
                continue

            hinted = hint_reason(f)
            blocking = (audit.obstructions(f.source.bbox)
                        if audit and f.source and f.source.bbox else [])

            if blocking:
                defect, cover = blocking[0]
                reason = "occluded_by_seal" if defect.kind == "seal" else "overwritten"
                detail = (f"{REASONS[reason]} — measured over {cover * 100:.0f}% of the "
                          f"writing; refused despite a read confidence of "
                          f"{f.confidence:.2f}, because the page itself does not "
                          f"support it")
                _refuse(f, d.doc_id, reason, detail)
            elif hinted:
                _refuse(f, d.doc_id, hinted,
                        f"{REASONS[hinted]}, per the extractor's own note")
            elif audit and f.status != "refused" and f.confidence < REGISTER_REFUSE_BELOW:
                _refuse(f, d.doc_id, "low_confidence",
                        f"{REASONS['low_confidence']}: read at {f.confidence:.2f}, "
                        f"below the {REGISTER_REFUSE_BELOW:.2f} bar this page type "
                        f"carries (printed paper is accepted at {REFUSE_BELOW:.2f})")
            elif f.status != "refused":
                continue

            if image:
                _attach_crop(f, image)
    return drafts
