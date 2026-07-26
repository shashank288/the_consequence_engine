"""Deterministic sequencing engine — the Consequence Engine's spine.

Pure logic: no network, no Sarvam. Input ObligationDrafts, output a Plan with
visible, quotable blocking edges, duplicate collapsing, an unknown bucket,
refusals, and exactly one next action.

Hardened for real extracted data (M2): dependency cycles are detected and
broken deterministically instead of silently producing no next action, mixed
date formats are normalised before ordering, duplicate detection survives
"Canara Bank" vs "Canara Bank Ltd, Khammam Branch" without merging two
genuinely different obligations, and mismatch classification handles N
readings and two scripts — refusing to call a pair cosmetic unless it can
prove it.

Owned by feat/sequencer. Acceptance: tests/test_sequencer.py passes.
"""
from __future__ import annotations

from ..config import REFUSE_BELOW
from ..contracts import (BlockingEdge, Case, FieldReading, Mismatch,
                         ObligationDraft, Plan, PlanItem, Requirement,
                         SourceRef)
from .dates import UNDATED, due_iso
from .text import (containment, content_tokens, cross_script_verdict,
                   has_devanagari, jaccard, norm, office_relation)

# --- duplicate-collapse thresholds ------------------------------------------
# Two obligations fold into one only when the asker matches AND both the
# containment and the overlap tests agree. Containment alone over-merges a
# short ask into any longer ask that repeats its words; the Jaccard floor is
# the guard. Under-merging shows a redundant item — over-merging DELETES an
# obligation from the plan, so the guard is deliberately conservative.
DUP_CONTAINMENT = 0.6
DUP_JACCARD = 0.4
# When we cannot tell who is asking, only near-identical asks may fold.
DUP_CONTAINMENT_UNKNOWN_ASKER = 0.85
DUP_JACCARD_UNKNOWN_ASKER = 0.7

_SEVERITY = {"cosmetic": 0, "unknown": 1, "blocking": 2}


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


# --- mismatch classification (card 17) --------------------------------------

def _classify_pair(a: str, b: str) -> tuple[str, str]:
    """Cosmetic only when we can show it; otherwise blocking or an honest
    'unknown'. Never returns cosmetic on a guess."""
    if norm(a) == norm(b):
        return ("cosmetic",
                "readings differ only in capitalisation, spacing or punctuation")
    if has_devanagari(a) != has_devanagari(b):
        return cross_script_verdict(a, b)

    aw, bw = norm(a).split(), norm(b).split()
    if not aw or not bw:
        return "unknown", "one reading is empty"
    short, long_ = (aw, bw) if len(" ".join(aw)) <= len(" ".join(bw)) else (bw, aw)
    if short[0] == long_[0] and all(
        any(lw.startswith(w) for lw in long_) for w in short
    ):
        return ("cosmetic",
                "same leading name; remaining parts are initials/expansions of the longer form")
    return "blocking", "readings differ beyond transliteration or initial expansion"


def _classify_readings(values: list[str]) -> tuple[str, str]:
    """Worst verdict across ALL pairs — with three readings, one bad pair is
    enough to make the field unsafe."""
    worst, reason = None, ""
    for i in range(len(values)):
        for j in range(i + 1, len(values)):
            cls, why = _classify_pair(values[i], values[j])
            if worst is None or _SEVERITY[cls] > _SEVERITY[worst]:
                worst, reason = cls, f"'{values[i]}' vs '{values[j]}': {why}"
    return (worst or "unknown", reason or "only one reading")


def _find_mismatches(drafts) -> list[Mismatch]:
    by_name: dict[str, list[FieldReading]] = {}
    for d in drafts:
        for f in d.identity_fields:
            if f.status == "read" and f.value:
                by_name.setdefault(f.name, []).append(f)
    out: list[Mismatch] = []
    for name, fs in by_name.items():
        # Distinct on the EXACT words on the page: a capitalisation-only
        # difference is still two different readings, shown and classified
        # cosmetic rather than quietly folded away.
        distinct: dict[str, FieldReading] = {}
        for f in fs:
            distinct.setdefault((f.value or "").strip(), f)
        if len(distinct) > 1:
            cls, reason = _classify_readings(list(distinct.keys()))
            out.append(Mismatch(field_name=name, readings=list(distinct.values()),
                                classification=cls, reason=reason))
    return out


# --- duplicate collapsing ----------------------------------------------------

def _is_duplicate(keeper: ObligationDraft, other: ObligationDraft) -> bool:
    rel = office_relation(keeper.asked_by, other.asked_by)
    if rel == "different":
        return False
    ta, tb = content_tokens(keeper.asked_what), content_tokens(other.asked_what)
    if min(len(ta), len(tb)) < 2:               # too little text to judge safely
        return norm(keeper.asked_what) == norm(other.asked_what)
    c = containment(keeper.asked_what, other.asked_what)
    j = jaccard(keeper.asked_what, other.asked_what)
    if rel == "same":
        return c >= DUP_CONTAINMENT and j >= DUP_JACCARD
    return c >= DUP_CONTAINMENT_UNKNOWN_ASKER and j >= DUP_JACCARD_UNKNOWN_ASKER


def _absorb(keeper: ObligationDraft, dropped: ObligationDraft) -> None:
    """A folded duplicate's requirements must not vanish: the two pages
    describe one obligation, so the surviving item carries both pages' needs
    and provides. Dropping a requirement here would under-block the plan."""
    have = {n.key for n in keeper.needs}
    keeper.needs += [n for n in dropped.needs if n.key not in have]
    keeper.provides += [p for p in dropped.provides if p not in keeper.provides]


# --- cycle detection ---------------------------------------------------------

def _find_cycle(adj: dict[str, set[str]]) -> list[str] | None:
    """One cycle as a node list (deterministic order), or None. Iterative DFS —
    a self-loop (A needs what A itself provides) returns [A]."""
    state: dict[str, int] = {}                  # 0 = on the current path, 1 = finished
    for root in sorted(adj):
        if state.get(root) is not None:
            continue
        state[root] = 0
        path = [root]
        stack = [(root, iter(sorted(adj.get(root, ()))))]
        while stack:
            node, children = stack[-1]
            nxt = next(children, None)
            if nxt is None:
                state[node] = 1
                stack.pop()
                path.pop()
                continue
            if state.get(nxt) == 0:
                return path[path.index(nxt):]
            if state.get(nxt) == 1:
                continue
            state[nxt] = 0
            path.append(nxt)
            stack.append((nxt, iter(sorted(adj.get(nxt, ())))))
    return None


def _break_cycles(graph: dict[str, dict[str, str]],
                  due_by_id: dict[str, str]) -> dict[str, dict[str, tuple[str, list[str]]]]:
    """Waive one item's in-loop dependencies per cycle so the plan always has a
    way forward. The waiver is deterministic — earliest readable deadline wins,
    ties broken by id — and every waived dependency is still shown as an edge.

    Returns {item_id: {need_key: (blocker_id, cycle_ids)}}.
    """
    adj = {n: set(deps.values()) for n, deps in graph.items()}
    waived: dict[str, dict[str, tuple[str, list[str]]]] = {}
    while True:
        cycle = _find_cycle(adj)
        if cycle is None:
            return waived
        breaker = min(cycle, key=lambda n: (due_by_id.get(n, UNDATED), n))
        in_loop = {k: b for k, b in graph[breaker].items() if b in cycle}
        waived.setdefault(breaker, {}).update(
            {k: (b, list(cycle)) for k, b in in_loop.items()})
        adj[breaker] = {b for b in adj[breaker] if b not in cycle}


def _cycle_reason(d: ObligationDraft, need: Requirement, blocker_id: str,
                  cycle: list[str], due: str) -> str:
    choice = (f"it carries the earliest stated deadline ({due})" if due != UNDATED
              else "no item in the loop has a readable deadline, so the lowest id was taken")
    if len(cycle) == 1:
        return (f'Self-referential requirement: "{need.quote}" — {d.asked_by} asks '
                f"{d.id} for '{need.key}', which only {d.id} itself provides. No "
                f"supplied page breaks the loop; treating {d.id} as startable and "
                f"flagging this for human check.")
    return (f'Circular requirement ({" -> ".join(cycle)} -> {cycle[0]}): '
            f'"{need.quote}" — required by {d.asked_by}, but {blocker_id} in turn '
            f"waits on {d.id}. No supplied page breaks the loop; starting with "
            f"{d.id} because {choice}. Flagged for human check.")


def _no_action_statement(items: dict[str, PlanItem]) -> str:
    """There is ALWAYS a next single action, or an honest sentence saying why
    not. Silence (None) would read on screen as 'nothing to do'."""
    if not items:
        return "No documents in this case yet — nothing to sequence."
    blocked = [i for i in items.values() if i.state == "blocked"]
    unknown = [i for i in items.values() if i.state == "unknown"]
    if blocked:
        keys = sorted({k for i in blocked for k in i.needs_docs})
        tail = f"; {len(unknown)} item(s) are still unclassified" if unknown else ""
        if not keys:
            return ("Nothing can be started yet: every remaining item is waiting on "
                    f"a requirement no supplied paper provides{tail}. Human review needed.")
        return ("Nothing can be started yet: every remaining item waits on "
                + ", ".join(keys) + f", and no supplied paper provides "
                + ("it" if len(keys) == 1 else "them") + f"{tail}. Human review needed.")
    if unknown:
        return (f"{len(unknown)} item(s) could not be classified from the photographs "
                "— a human must read them before this case can be sequenced.")
    return "Every item in this case is marked done — nothing left to do."


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

    # 2. duplicate collapsing (same asker + same ask; first kept, needs merged)
    kept: list[ObligationDraft] = []
    for d in known:
        dup = next((k for k in kept if _is_duplicate(k, d)), None)
        if dup is not None:
            items[d.id] = PlanItem(obligation_id=d.id, state="duplicate",
                                   duplicate_of=dup.id)
            _absorb(dup, d)
        else:
            kept.append(d)

    by_id = {d.id: d for d in kept}
    provides_map = {p: d.id for d in kept for p in d.provides}
    due_by_id = {d.id: due_iso(d.due) for d in kept}

    # 3. done via mock status lookup
    for d in kept:
        if d.provides and all(p in case.done_keys for p in d.provides):
            items[d.id] = PlanItem(obligation_id=d.id, state="done")
    done_ids = {i.obligation_id for i in items.values() if i.state == "done"}

    # 4. dependency graph over what is still open, then cycle-break it
    graph: dict[str, dict[str, str]] = {}
    for d in kept:
        if d.id in done_ids:
            continue
        deps = {}
        for need in d.needs:
            if need.key in satisfied:
                continue
            blocker = provides_map.get(need.key)
            if blocker is not None and blocker not in done_ids:
                deps[need.key] = blocker
        graph[d.id] = deps
    waivers = _break_cycles(graph, due_by_id)

    # 5. blocking edges with quotable evidence
    for d in kept:
        if d.id in items:                       # done items keep their state
            continue
        blocking: list[Requirement] = []
        looped: list[str] = []
        for need in d.needs:
            if need.key in satisfied:
                continue
            waived = waivers.get(d.id, {})
            if need.key in waived:
                blocker_id, cycle = waived[need.key]
                other = by_id.get(blocker_id)
                evidence: list[SourceRef] = [need.source]
                if other is not None and other.id != d.id:
                    evidence += [n.source for n in other.needs
                                 if graph.get(blocker_id, {}).get(n.key) in cycle]
                edges.append(BlockingEdge(
                    blocked_id=d.id, blocker_id=blocker_id, need_key=need.key,
                    reason=_cycle_reason(d, need, blocker_id, cycle, due_by_id[d.id]),
                    evidence=evidence))
                looped.append(need.key)         # visible, but not blocking
                continue

            blocker = provides_map.get(need.key)
            if blocker is not None and blocker not in done_ids:
                evidence = [need.source]
                for m in mismatches:            # attach both readings when relevant
                    if m.field_name in need.key or "match" in need.key:
                        evidence += [r.source for r in m.readings if r.source]
                edges.append(BlockingEdge(
                    blocked_id=d.id, blocker_id=blocker, need_key=need.key,
                    reason=f'"{need.quote}" — required by {d.asked_by}; not yet satisfied',
                    evidence=evidence))
            blocking.append(need)

        if blocking:
            items[d.id] = PlanItem(obligation_id=d.id, state="blocked",
                                   needs_docs=[n.key for n in blocking] + looped)
        else:
            items[d.id] = PlanItem(obligation_id=d.id, state="actionable",
                                   next_action=d.asked_what, needs_docs=looped)

    # 6. order actionable by normalised due date, then id; pick THE next action
    actionable = [d for d in kept if items[d.id].state == "actionable"]
    for i, d in enumerate(sorted(actionable, key=lambda x: (due_by_id[x.id], x.id)),
                          start=1):
        items[d.id].order = i

    first = next((items[d.id] for d in actionable if items[d.id].order == 1), None)
    next_action = first.next_action if first else _no_action_statement(items)

    return Plan(case_id=case.id, items=list(items.values()), edges=edges,
                mismatches=mismatches, refusals=refusals,
                next_single_action=next_action)
