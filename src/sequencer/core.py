"""Deterministic sequencing engine — the Consequence Engine's spine.

Pure logic: no network, no Sarvam. Input ObligationDrafts, output a Plan with
visible, quotable blocking edges, duplicate collapsing, an unknown bucket,
refusals, and exactly one next action.

Owned by feat/sequencer. Acceptance: tests/test_sequencer.py passes.
"""
from __future__ import annotations

import re

from ..config import REFUSE_BELOW
from ..contracts import (BlockingEdge, Case, FieldReading, Mismatch, Plan,
                         PlanItem)


def _norm(s: str | None) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())).strip()


def _tokens(s: str | None) -> set[str]:
    return set(_norm(s).split())


def _similar(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


def _apply_refusals(drafts) -> list[FieldReading]:
    """Below-threshold consequential fields are refused, never guessed."""
    refusals: list[FieldReading] = []
    for d in drafts:
        for f in [d.due, d.amount, *d.identity_fields]:
            if f is None:
                continue
            if f.value is not None and f.confidence < REFUSE_BELOW:
                f.status, f.value = "refused", None
            if f.status == "refused":
                refusals.append(f)
    return refusals


def _classify_pair(a: str, b: str) -> tuple[str, str]:
    """Card-17 mechanic: transliteration/initial variants are cosmetic; else blocking."""
    aw, bw = _norm(a).split(), _norm(b).split()
    if not aw or not bw:
        return "unknown", "one reading is empty"
    short, long_ = (aw, bw) if len(" ".join(aw)) <= len(" ".join(bw)) else (bw, aw)
    if short[0] == long_[0] and all(
        any(lw.startswith(w.rstrip(".")) for lw in long_) for w in short
    ):
        return ("cosmetic",
                "same leading name; remaining parts are initials/expansions of the longer form")
    return "blocking", "readings differ beyond transliteration or initial expansion"


def _find_mismatches(drafts) -> list[Mismatch]:
    by_name: dict[str, list[FieldReading]] = {}
    for d in drafts:
        for f in d.identity_fields:
            if f.status == "read" and f.value:
                by_name.setdefault(f.name, []).append(f)
    out: list[Mismatch] = []
    for name, fs in by_name.items():
        distinct = {}
        for f in fs:
            distinct.setdefault(_norm(f.value), f)
        if len(distinct) > 1:
            vals = list(distinct.keys())
            cls, reason = _classify_pair(vals[0], vals[1])
            out.append(Mismatch(field_name=name, readings=list(distinct.values()),
                                classification=cls, reason=reason))
    return out


def build_plan(case: Case) -> Plan:
    drafts = [d.model_copy(deep=True) for d in case.drafts]
    refusals = _apply_refusals(drafts)
    mismatches = _find_mismatches(drafts)
    satisfied = set(case.provided_facts) | set(case.done_keys)

    items: dict[str, PlanItem] = {}
    edges: list[BlockingEdge] = []

    # 1. unknown bucket — surfaced, never dropped
    known = []
    for d in drafts:
        if d.unknown:
            items[d.id] = PlanItem(obligation_id=d.id, state="unknown")
        else:
            known.append(d)

    # 2. duplicate collapsing (same asker + similar ask; first kept)
    kept = []
    for d in known:
        dup = next((k for k in kept
                    if _norm(k.asked_by) == _norm(d.asked_by)
                    and _similar(k.asked_what, d.asked_what) >= 0.6), None)
        if dup is not None:
            items[d.id] = PlanItem(obligation_id=d.id, state="duplicate",
                                   duplicate_of=dup.id)
        else:
            kept.append(d)

    provides_map = {p: d.id for d in kept for p in d.provides}

    # 3. done via mock status lookup
    for d in kept:
        if d.provides and all(p in case.done_keys for p in d.provides):
            items[d.id] = PlanItem(obligation_id=d.id, state="done")

    # 4. blocking edges with quotable evidence
    for d in kept:
        if d.id in items:
            continue
        blocking = []
        for need in d.needs:
            if need.key in satisfied:
                continue
            blocker = provides_map.get(need.key)
            if blocker is not None and items.get(blocker,
                    PlanItem(obligation_id=blocker, state="actionable")).state != "done":
                evidence = [need.source]
                for m in mismatches:               # attach both readings when relevant
                    if m.field_name in need.key or "match" in need.key:
                        evidence += [r.source for r in m.readings if r.source]
                edges.append(BlockingEdge(
                    blocked_id=d.id, blocker_id=blocker, need_key=need.key,
                    reason=f'"{need.quote}" — required by {d.asked_by}; not yet satisfied',
                    evidence=evidence))
            blocking.append(need)
        if blocking:
            items[d.id] = PlanItem(obligation_id=d.id, state="blocked",
                                   needs_docs=[n.key for n in blocking])
        else:
            items[d.id] = PlanItem(obligation_id=d.id, state="actionable",
                                   next_action=d.asked_what)

    # 5. order actionable by due date, then id; pick THE one next action
    def _due_key(d):
        f = d.due
        v = f.value if (f and f.status == "read" and f.value) else "9999-12-31"
        return (v, d.id)

    for i, d in enumerate(sorted((k for k in kept if items[k.id].state == "actionable"),
                                 key=_due_key), start=1):
        items[d.id].order = i

    first = next((items[d.id] for d in kept
                  if items[d.id].state == "actionable" and items[d.id].order == 1), None)

    return Plan(case_id=case.id, items=list(items.values()), edges=edges,
                mismatches=mismatches, refusals=refusals,
                next_single_action=first.next_action if first else None)
