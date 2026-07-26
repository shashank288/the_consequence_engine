"""Does this page contradict the last accepted entry for the same plot?

Card 87's second demo beat. The register page in the applicant's hand and the
record the office holds are two claims about the same plot; when they disagree
the mutation gets rejected at the counter, and the family finds out after the
queue rather than before it.

Rules of engagement, in the spirit of the refusal policy:

* We only compare where we can say WHICH plot we are talking about. A page
  reading is matched to a record by plot/survey number, exactly — never fuzzily.
* We only raise a flag we can defend. `cross_script_verdict` proves a match or
  admits it cannot tell; a proven match raises nothing, because a system that
  cries wolf on "लक्ष्मम्मा" vs "Lakshmamma" trains its user to ignore it.
* A refused reading still contradicts. If the page's owner cell is struck
  through and we refused it, the record's entry is still the only accepted name
  and the human has to be told which is current.
"""
from __future__ import annotations

from ..contracts import FieldReading, Mismatch, ObligationDraft, SourceRef
from ..sequencer.text import cross_script_verdict, has_devanagari, norm, skeleton
from .policy import is_register
from .reader import base_name
from .records import prior_record

PLOT_FIELDS = ("plot_no", "survey_no")
OWNER_FIELD = "owner_name"
ROW_TOLERANCE = 0.012            # normalised page height; two readings on one line


def _y_centre(f: FieldReading) -> float | None:
    if f.source and f.source.bbox and len(f.source.bbox) == 4:
        return (f.source.bbox[1] + f.source.bbox[3]) / 2
    return None


def _pair_rows(draft: ObligationDraft) -> list[tuple[FieldReading, list[FieldReading]]]:
    """Pair each plot number with the owner name(s) written on its own line.

    A register page holds several plots. Associating an owner with the wrong
    row would manufacture a contradiction, so rows are paired by geometry (the
    two readings share a horizontal band) and, only when the page carries a
    single plot, by that being unambiguous.
    """
    plots = [f for f in draft.identity_fields
             if base_name(f.name) in PLOT_FIELDS and (f.value or "").strip()]
    owners = [f for f in draft.identity_fields if base_name(f.name) == OWNER_FIELD]
    if not plots or not owners:
        return []

    placed = [(p, _y_centre(p)) for p in plots]
    if len(plots) == 1 and all(y is None for _, y in placed):
        return [(plots[0], owners)]

    rows: list[tuple[FieldReading, list[FieldReading]]] = []
    for plot, py in placed:
        if py is None:
            continue
        same_line = [o for o in owners
                     if (oy := _y_centre(o)) is not None
                     and abs(oy - py) <= ROW_TOLERANCE]
        if same_line:
            rows.append((plot, same_line))
    return rows


def _compare(page_value: str, record_value: str) -> tuple[str, str]:
    """('cosmetic'|'unknown'|'blocking', why). Cosmetic means PROVEN same name."""
    if norm(page_value) == norm(record_value):
        return "cosmetic", "the page and the record hold the same name"
    if has_devanagari(page_value) != has_devanagari(record_value):
        return cross_script_verdict(page_value, record_value)
    if skeleton(page_value) and skeleton(page_value) == skeleton(record_value):
        return ("cosmetic",
                "same name, different spelling — the consonant skeletons match")
    return ("blocking",
            "the page names a different person than the last accepted entry")


def _record_reading(plot: str, rec: dict) -> FieldReading:
    """The records system's entry, carried as a reading so the UI can show both
    sides of the contradiction with provenance."""
    return FieldReading(
        name=OWNER_FIELD, value=rec["owner_name"], confidence=1.0, status="read",
        source=SourceRef(doc_id=f"prior_record:{plot}", page=1,
                         quote=f"last accepted entry for {plot} "
                               f"({rec.get('entry_year', 'year not stated')}): "
                               f"{rec['owner_name']}"))


def check_contradictions(drafts) -> list[Mismatch]:
    """Every place this page disagrees with the records system, with the reason.

    Returns `Mismatch`es shaped exactly like the sequencer's own, so the plan
    surfaces them through the existing mismatch panel with no contract change.
    """
    out: list[Mismatch] = []
    for draft in drafts:
        if not is_register(draft):
            continue
        for plot, owners in _pair_rows(draft):
            rec = prior_record(plot.value)
            if rec is None or not rec.get("owner_name"):
                continue                       # not on file: nothing to contradict
            entry = _record_reading(plot.value, rec)

            for owner in owners:
                # Copy: a Mismatch is plan-level output and must never be a
                # handle onto the stored draft's reading.
                shown = owner.model_copy(deep=True)
                if owner.status == "refused":
                    why = (owner.source.quote if owner.source and owner.source.quote
                           else "the cell could not be read safely")
                    out.append(Mismatch(
                        field_name=OWNER_FIELD, readings=[shown, entry],
                        classification="blocking",
                        reason=(f"Plot {plot.value}: this page's owner entry could not "
                                f"be read safely, and the records system still holds "
                                f"'{rec['owner_name']}' from "
                                f"{rec.get('entry_year', 'an unstated year')}. Which name "
                                f"is current cannot be settled from this page — a human "
                                f"must confirm it before the mutation is filed. "
                                f"Evidence: {why}")))
                    continue
                if not (owner.value or "").strip():
                    continue
                cls, why = _compare(owner.value, rec["owner_name"])
                if cls == "cosmetic":
                    continue                   # proven the same name: no flag
                out.append(Mismatch(
                    field_name=OWNER_FIELD, readings=[shown, entry],
                    classification=cls,
                    reason=(f"Plot {plot.value}: the page reads '{owner.value}', the last "
                            f"accepted entry ({rec.get('entry_year', 'year not stated')}) "
                            f"reads '{rec['owner_name']}' — {why}")))
    return out
