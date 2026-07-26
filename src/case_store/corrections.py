"""Correction propagation — the Memory L4 demo beat.

Patch every reading of (doc_id, field_name), re-derive the plan, then report
EXACTLY what moved by diffing the plan before against the plan after.
`Correction.propagated_to` is that diff's obligation list — computed, never
guessed.

Consistent with the refusal policy: if no reading matches the target, the
correction is REFUSED (`CorrectionTargetNotFound`, with the available targets)
instead of being recorded as a silent no-op.

Pure logic — no network, no I/O. Persistence lives in store.py.
"""
from __future__ import annotations

from ..contracts import Case, Correction, FieldReading, ObligationDraft, Plan
from ..sequencer.core import build_plan


class CorrectionTargetNotFound(LookupError):
    """No FieldReading matches (doc_id, field_name)."""

    def __init__(self, doc_id: str, field_name: str, available: list[dict]) -> None:
        self.doc_id, self.field_name, self.available = doc_id, field_name, available
        super().__init__(f"no '{field_name}' reading sourced from doc '{doc_id}'")


def _readings(d: ObligationDraft) -> list[FieldReading]:
    return [f for f in (d.due, d.amount, *d.identity_fields) if f is not None]


def _target_doc(f: FieldReading, d: ObligationDraft) -> str:
    """Doc a user would name to correct this reading: where it was READ FROM
    (an ID card reading can sit on a checklist obligation), else the item's doc."""
    return f.source.doc_id if (f.source and f.source.doc_id) else d.doc_id


def _source_key(f: FieldReading) -> tuple[str, str | None]:
    """Reading identity that survives the sequencer's deep copy — used to map
    plan-level mismatches/refusals back to the obligations that carry them."""
    return (f.name, f.source.doc_id if f.source else None)


def correction_targets(case: Case) -> list[dict]:
    """Every (doc_id, field_name) a correction can address. Returned with the
    refusal so a mistyped doc id gets a menu instead of a no-op."""
    rows = [{"doc_id": _target_doc(f, d), "field_name": f.name, "obligation_id": d.id,
             "current_value": f.value, "status": f.status}
            for d in case.drafts for f in _readings(d)]
    return sorted(rows, key=lambda t: (t["doc_id"], t["field_name"], t["obligation_id"]))


def _owners(case: Case) -> dict[tuple[str, str | None], set[str]]:
    owners: dict[tuple[str, str | None], set[str]] = {}
    for d in case.drafts:
        for f in _readings(d):
            owners.setdefault(_source_key(f), set()).add(d.id)
    return owners


def _evidence_sig(refs) -> tuple:
    return tuple(sorted((s.doc_id, s.page, s.quote or "", s.crop_path or "") for s in refs))


_BLANK = {"state": None, "order": None, "next_action": None, "duplicate_of": None,
          "needs_docs": (), "blocked_by": {}, "blocks": frozenset(),
          "mismatches": {}, "refusals": frozenset()}


def _fingerprint(plan: Plan, owners: dict) -> dict[str, dict]:
    """Per-obligation snapshot of everything the plan says about it."""
    fp: dict[str, dict] = {}

    def slot(oid: str) -> dict:
        if oid not in fp:
            fp[oid] = {"state": None, "order": None, "next_action": None,
                       "duplicate_of": None, "needs_docs": (), "blocked_by": {},
                       "blocks": set(), "mismatches": {}, "refusals": set()}
        return fp[oid]

    for it in plan.items:
        slot(it.obligation_id).update(state=it.state, order=it.order,
                                      next_action=it.next_action,
                                      duplicate_of=it.duplicate_of,
                                      needs_docs=tuple(it.needs_docs))
    for e in plan.edges:
        slot(e.blocked_id)["blocked_by"][(e.blocker_id, e.need_key)] = (
            e.reason, _evidence_sig(e.evidence))
        slot(e.blocker_id)["blocks"].add((e.blocked_id, e.need_key))
    for m in plan.mismatches:
        oids = {o for r in m.readings for o in owners.get(_source_key(r), ())}
        for oid in oids:
            slot(oid)["mismatches"][m.field_name] = (
                m.classification, tuple(r.value for r in m.readings), tuple(sorted(oids)))
    for r in plan.refusals:
        for oid in owners.get(_source_key(r), ()):
            slot(oid)["refusals"].add(r.name)
    return fp


def _mismatch_entry(m, owners: dict) -> dict:
    return {"field_name": m.field_name, "classification": m.classification,
            "values": [r.value for r in m.readings],
            "obligations": sorted({o for r in m.readings
                                   for o in owners.get(_source_key(r), ())})}


def _edge_entry(e) -> dict:
    return {"blocked_id": e.blocked_id, "blocker_id": e.blocker_id,
            "need_key": e.need_key, "reason": e.reason}


def _refusal_entry(r) -> dict:
    return {"name": r.name, "doc_id": r.source.doc_id if r.source else None,
            "confidence": r.confidence}


def _obligation_changes(oid: str, b: dict, a: dict) -> list[str]:
    out: list[str] = []
    if b["state"] != a["state"]:
        out.append(f"state {b['state']} → {a['state']}")
    if b["order"] != a["order"]:
        out.append(f"order {b['order']} → {a['order']}")
    if b["duplicate_of"] != a["duplicate_of"]:
        out.append(f"duplicate_of {b['duplicate_of']} → {a['duplicate_of']}")
    if b["needs_docs"] != a["needs_docs"]:
        out.append(f"unmet needs {list(b['needs_docs'])} → {list(a['needs_docs'])}")
    if b["next_action"] != a["next_action"]:
        out.append("next-action text changed")

    bb, ab = b["blocked_by"], a["blocked_by"]
    for k in sorted(set(bb) - set(ab)):
        out.append(f"no longer blocked by {k[0]} ({k[1]})")
    for k in sorted(set(ab) - set(bb)):
        out.append(f"now blocked by {k[0]} ({k[1]})")
    for k in sorted(set(ab) & set(bb)):
        if ab[k] != bb[k]:
            out.append(f"evidence for the {k[0]} → {oid} edge changed ({k[1]})")
    for k in sorted(set(a["blocks"]) ^ set(b["blocks"])):
        verb = "now blocks" if k in a["blocks"] else "no longer blocks"
        out.append(f"{verb} {k[0]} ({k[1]})")

    bm, am = b["mismatches"], a["mismatches"]
    for f in sorted(set(bm) - set(am)):
        out.append(f"{f} mismatch resolved")
    for f in sorted(set(am) - set(bm)):
        out.append(f"new {am[f][0]} mismatch on {f}")
    for f in sorted(set(am) & set(bm)):
        if bm[f][0] != am[f][0]:
            out.append(f"{f} mismatch reclassified {bm[f][0]} → {am[f][0]}")
        elif bm[f][1] != am[f][1]:
            out.append(f"{f} mismatch readings changed to {list(am[f][1])}")
        elif bm[f][2] != am[f][2]:
            out.append(f"{f} mismatch now spans {list(am[f][2])}")

    for n in sorted(set(b["refusals"]) - set(a["refusals"])):
        out.append(f"{n} no longer refused")
    for n in sorted(set(a["refusals"]) - set(b["refusals"])):
        out.append(f"{n} now refused")
    return out


def _plan_summary(diff: dict) -> str:
    bits: list[str] = []
    for m in diff["mismatches_cleared"]:
        who = "↔".join(m["obligations"])
        bits.append(f"cleared the {who + ' ' if who else ''}{m['classification']} "
                    f"mismatch on {m['field_name']}")
    for m in diff["mismatches_added"]:
        bits.append(f"raised a new {m['classification']} mismatch on {m['field_name']}")
    for o in diff["obligations"]:
        b, a = o["state_before"], o["state_after"]
        if b == a:
            continue
        bits.append(f"unblocked {o['obligation_id']}" if (b == "blocked" and a == "actionable")
                    else f"{o['obligation_id']}: {b} → {a}")
    for r in diff["refusals_cleared"]:
        bits.append(f"{r['name']} is no longer refused")
    for r in diff["refusals_added"]:
        bits.append(f"{r['name']} is now refused")
    for e in diff["edges_removed"]:
        bits.append(f"dropped the {e['blocker_id']} → {e['blocked_id']} blocking edge")
    for e in diff["edges_added"]:
        bits.append(f"added a {e['blocker_id']} → {e['blocked_id']} blocking edge")
    if not bits:
        return ("no plan movement — the value is recorded and applies to every "
                "later check")
    head = "; ".join(bits)
    if diff["next_single_action_before"] != diff["next_single_action_after"]:
        return f"{head}. Next single action is now: {diff['next_single_action_after']}"
    return f"{head}. Next single action unchanged"


def diff_plans(case: Case, before: Plan, after: Plan) -> dict:
    """What changed between two plans of the same case, per obligation.

    `case` supplies only the reading→obligation index (names and source docs,
    which a correction never changes), so one index is valid for both plans.
    """
    owners = _owners(case)
    fb, fa = _fingerprint(before, owners), _fingerprint(after, owners)

    obligations = []
    for oid in sorted(set(fb) | set(fa)):
        b, a = fb.get(oid, _BLANK), fa.get(oid, _BLANK)
        changes = _obligation_changes(oid, b, a)
        if changes:
            obligations.append({"obligation_id": oid, "changes": changes,
                                "state_before": b["state"], "state_after": a["state"],
                                "order_before": b["order"], "order_after": a["order"]})

    mb = {m.field_name: m for m in before.mismatches}
    ma = {m.field_name: m for m in after.mismatches}
    eb = {(e.blocked_id, e.blocker_id, e.need_key): e for e in before.edges}
    ea = {(e.blocked_id, e.blocker_id, e.need_key): e for e in after.edges}
    rb = {(r.name, r.source.doc_id if r.source else None): r for r in before.refusals}
    ra = {(r.name, r.source.doc_id if r.source else None): r for r in after.refusals}

    diff = {
        "propagated_to": [o["obligation_id"] for o in obligations],
        "obligations": obligations,
        "mismatches_cleared": [_mismatch_entry(mb[f], owners) for f in sorted(set(mb) - set(ma))],
        "mismatches_added": [_mismatch_entry(ma[f], owners) for f in sorted(set(ma) - set(mb))],
        "mismatches_reclassified": [
            {"field_name": f, "from": mb[f].classification, "to": ma[f].classification}
            for f in sorted(set(mb) & set(ma))
            if mb[f].classification != ma[f].classification],
        "edges_removed": [_edge_entry(eb[k]) for k in sorted(set(eb) - set(ea))],
        "edges_added": [_edge_entry(ea[k]) for k in sorted(set(ea) - set(eb))],
        "refusals_cleared": [_refusal_entry(rb[k]) for k in sorted(
            set(rb) - set(ra), key=lambda k: (k[0], k[1] or ""))],
        "refusals_added": [_refusal_entry(ra[k]) for k in sorted(
            set(ra) - set(rb), key=lambda k: (k[0], k[1] or ""))],
        "next_single_action_before": before.next_single_action,
        "next_single_action_after": after.next_single_action,
        "patched_readings": [],
    }
    diff["plan_summary"] = _plan_summary(diff)
    diff["summary"] = diff["plan_summary"]
    return diff


def apply_correction(case: Case, doc_id: str, field_name: str, new: str
                     ) -> tuple[Case, Correction, dict]:
    """Patch → re-sequence → diff. Mutates `case` (drafts, plan, corrections)
    and returns (case, correction, diff). Caller persists.

    Raises CorrectionTargetNotFound if the target does not exist.
    """
    before = build_plan(case)          # re-derived, so the diff isolates THIS correction

    patched: list[dict] = []
    for d in case.drafts:
        for f in _readings(d):
            if f.name == field_name and _target_doc(f, d) == doc_id:
                patched.append({"obligation_id": d.id, "doc_id": doc_id,
                                "field_name": field_name, "old": f.value,
                                "old_status": f.status, "old_confidence": f.confidence,
                                "new": new})
                # human-confirmed: full confidence, and out of the refusal queue
                f.value, f.status, f.confidence = new, "read", 1.0
    if not patched:
        raise CorrectionTargetNotFound(doc_id, field_name, correction_targets(case))

    case.plan = build_plan(case)
    diff = diff_plans(case, before, case.plan)
    diff["patched_readings"] = patched
    old = next((p["old"] for p in patched if p["old"] is not None), None)
    diff["summary"] = (f"{field_name} on {doc_id}: "
                       f"{old!r} → {new!r} — {diff['plan_summary']}")

    correction = Correction(doc_id=doc_id, field_name=field_name, old=old, new=new,
                            propagated_to=diff["propagated_to"])
    case.corrections.append(correction)
    return case, correction, diff
