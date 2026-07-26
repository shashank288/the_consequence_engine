"""Hardening tests for the sequencer — the messy-real-data cases the staged
fixture does not cover. Pure logic, no Sarvam key needed.

Run: py -3.12 -m pytest -q
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.contracts import (Case, FieldReading, ObligationDraft, Requirement,
                           SourceRef)
from src.sequencer.core import build_plan
from src.sequencer.dates import to_iso
from src.sequencer.text import office_relation

# --- builders ---------------------------------------------------------------


def _src(doc="doc", quote="quote"):
    return SourceRef(doc_id=doc, page=1, quote=quote)


def _need(key, quote=None, doc="doc"):
    quote = quote or f"{key.replace('_', ' ')} is required"
    return Requirement(key=key, quote=quote, source=_src(doc, quote))


def _due(value, conf=0.95, doc="doc"):
    return FieldReading(name="deadline", value=value, confidence=conf,
                        status="read", source=_src(doc, f"by {value}"))


def _ident(name, value, conf=0.95, doc="doc"):
    return FieldReading(name=name, value=value, confidence=conf, status="read",
                        source=_src(doc, value))


def _draft(id, what, by="Tehsil office, Khammam", needs=(), provides=(),
           due=None, unknown=False, identity=()):
    return ObligationDraft(id=id, doc_id=f"{id}_doc", doc_type="test",
                           asked_what=what, asked_by=by, due=due,
                           needs=list(needs), provides=list(provides),
                           identity_fields=list(identity), unknown=unknown)


def _case(*drafts, provided=(), done=()):
    return Case(id="t", drafts=list(drafts), provided_facts=list(provided),
                done_keys=list(done))


def _states(plan):
    return {i.obligation_id: i for i in plan.items}


# --- 1. cycle safety --------------------------------------------------------

def test_cycle_still_produces_a_next_single_action():
    """A needs what B provides, B needs what A provides. Deadlock in the
    documents must not become silence on screen."""
    a = _draft("A", "Get the encumbrance certificate from the sub-registrar",
               needs=[_need("mutation_done", "mutation must be completed first")],
               provides=["ec_issued"], due=_due("2026-08-01"))
    b = _draft("B", "Submit the mutation application at the tehsil counter",
               needs=[_need("ec_issued", "encumbrance certificate must be enclosed")],
               provides=["mutation_done"], due=_due("2026-09-01"))
    plan = build_plan(_case(a, b))
    st = _states(plan)

    # earliest readable deadline wins the tie-break, deterministically
    assert st["A"].state == "actionable" and st["A"].order == 1
    assert plan.next_single_action == a.asked_what
    assert st["B"].state == "blocked"

    loop = next(e for e in plan.edges if "Circular requirement" in e.reason)
    assert loop.blocked_id == "A" and loop.blocker_id == "B"
    assert "2026-08-01" in loop.reason               # says WHY it started here
    assert len(loop.evidence) >= 2                   # both pages' words quoted
    assert "mutation_done" in st["A"].needs_docs     # loop stays visible on the item


def test_cycle_break_is_stable_when_no_deadline_is_readable():
    a = _draft("B2", "Task two", needs=[_need("k1")], provides=["k2"])
    b = _draft("A1", "Task one", needs=[_need("k2")], provides=["k1"])
    plan = build_plan(_case(a, b))
    st = _states(plan)
    assert st["A1"].state == "actionable"            # lowest id breaks the tie
    assert st["B2"].state == "blocked"
    assert plan.next_single_action == "Task one"


def test_self_referential_need_does_not_deadlock():
    a = _draft("S1", "Attach the updated record of rights",
               needs=[_need("record_updated")], provides=["record_updated"])
    plan = build_plan(_case(a))
    st = _states(plan)
    assert st["S1"].state == "actionable"
    assert plan.next_single_action == a.asked_what
    assert any("Self-referential" in e.reason for e in plan.edges)


def test_no_actionable_item_states_why_instead_of_going_silent():
    a = _draft("X1", "Submit the mutation application",
               needs=[_need("legal_heir_certificate")])
    plan = build_plan(_case(a))
    assert _states(plan)["X1"].state == "blocked"
    assert plan.next_single_action is not None
    assert "legal_heir_certificate" in plan.next_single_action
    assert "Nothing can be started yet" in plan.next_single_action


# --- 2. transitive blocking -------------------------------------------------

def _chain_case(done=()):
    return _case(
        _draft("C1", "Correct the name in the record of rights", provides=["name_ok"]),
        _draft("C2", "File the mutation application", needs=[_need("name_ok")],
               provides=["mutation_done"], due=_due("2026-08-20")),
        _draft("C3", "Complete the bank succession claim",
               needs=[_need("mutation_done")], provides=["bank_done"],
               due=_due("2026-09-10"), by="Canara Bank, Khammam branch"),
        _draft("C4", "Apply for the crop insurance payout", needs=[_need("bank_done")],
               due=_due("2026-09-30"), by="Agriculture office, Khammam"),
        done=done)


def test_four_deep_chain_unblocks_one_step_at_a_time():
    st = _states(build_plan(_chain_case()))
    assert st["C1"].state == "actionable" and st["C1"].order == 1
    assert [st[i].state for i in ("C2", "C3", "C4")] == ["blocked"] * 3

    st = _states(build_plan(_chain_case(done=["name_ok"])))
    assert st["C1"].state == "done"
    assert st["C2"].state == "actionable" and st["C2"].order == 1
    assert [st[i].state for i in ("C3", "C4")] == ["blocked", "blocked"]

    st = _states(build_plan(_chain_case(done=["name_ok", "mutation_done"])))
    assert [st[i].state for i in ("C1", "C2")] == ["done", "done"]
    assert st["C3"].state == "actionable" and st["C3"].order == 1
    assert st["C4"].state == "blocked"


def test_chain_edges_quote_the_requirement():
    plan = build_plan(_chain_case())
    e = next(e for e in plan.edges if e.blocked_id == "C4")
    assert e.blocker_id == "C3" and "bank done is required" in e.reason
    assert e.evidence and e.evidence[0].quote


# --- 3. duplicate robustness ------------------------------------------------

def test_near_duplicate_from_the_same_office_merges():
    letter = _draft("D1", "Complete succession claim on the deceased's bank account",
                    by="Canara Bank", needs=[_need("death_certificate")],
                    provides=["bank_done"], due=_due("2026-09-01"))
    sms = _draft("D2", "Complete succession claim formalities on the account",
                 by="Canara Bank Ltd, Khammam Branch",
                 needs=[_need("account_passbook")])
    st = _states(build_plan(_case(letter, sms)))
    assert st["D2"].state == "duplicate" and st["D2"].duplicate_of == "D1"
    # the folded page's requirement survives on the kept item
    assert set(st["D1"].needs_docs) == {"death_certificate", "account_passbook"}


def test_two_different_obligations_from_one_office_do_not_merge():
    a = _draft("E1", "Submit mutation application to transfer the plot into the heir's name")
    b = _draft("E2", "Submit affidavit of no objection from the other legal heirs",
               by="Tehsil Office Khammam (Land Records)")
    st = _states(build_plan(_case(a, b)))
    assert st["E1"].state == "actionable" and st["E2"].state == "actionable"
    assert all(i.state != "duplicate" for i in st.values())


def test_different_offices_never_merge_even_with_identical_asks():
    a = _draft("F1", "Complete succession claim on the account", by="Canara Bank, Khammam")
    b = _draft("F2", "Complete succession claim on the account", by="Canara Bank, Warangal")
    st = _states(build_plan(_case(a, b)))
    assert all(i.state != "duplicate" for i in st.values())


def test_unknown_asker_needs_a_near_identical_ask_to_merge():
    a = _draft("G1", "Complete succession claim on the deceased's bank account", by="unknown")
    b = _draft("G2", "Complete succession claim formalities on the account", by="unknown")
    st = _states(build_plan(_case(a, b)))
    assert all(i.state != "duplicate" for i in st.values())


def test_office_relation_cases():
    assert office_relation("Canara Bank", "Canara Bank Ltd, Khammam Branch") == "same"
    assert office_relation("Tehsil office, Khammam", "Tehsil office, Warangal") == "different"
    assert office_relation("unknown", "Canara Bank") == "unknown"


# --- 4. mismatch classification (card 17) -----------------------------------

def _mismatch_for(values, name="owner_name"):
    drafts = [_draft(f"M{i}", f"Task {i}", identity=[_ident(name, v, doc=f"d{i}")])
              for i, v in enumerate(values)]
    plan = build_plan(_case(*drafts))
    return next((m for m in plan.mismatches if m.field_name == name), None)


def test_case_and_spacing_only_difference_is_cosmetic():
    m = _mismatch_for(["SUSHILA DEVI", "Sushila  Devi."])
    assert m.classification == "cosmetic" and "capitalisation" in m.reason


def test_n_way_mismatch_takes_the_worst_pair():
    m = _mismatch_for(["Sushila D.", "SUSHILA DEVI", "Kamala Devi"])
    assert len(m.readings) == 3
    assert m.classification == "blocking"          # not just the first two
    assert "Kamala Devi" in m.reason


def test_devanagari_latin_same_name_is_cosmetic():
    m = _mismatch_for(["सुशीला देवी",
                       "Sushila Devi"])
    assert m.classification == "cosmetic" and "two scripts" in m.reason


def test_devanagari_latin_different_names_is_unknown_never_guessed_cosmetic():
    m = _mismatch_for(["राजेश कुमार",
                       "Sushila Devi"])
    assert m.classification == "unknown"           # honest, not a guess either way
    assert "human check" in m.reason


def test_two_different_devanagari_names_are_not_collapsed():
    """The old ASCII-only normaliser erased Devanagari entirely, making every
    Hindi reading look identical."""
    m = _mismatch_for(["सुशीला देवी",
                       "कमला देवी"])
    assert m is not None and m.classification == "blocking"


# --- 5. ordering ------------------------------------------------------------

def test_mixed_date_formats_order_by_real_date():
    plan = build_plan(_case(
        _draft("H1", "Pay the mutation fee at the counter", due=_due("01.09.2026")),
        _draft("H2", "Collect the encumbrance certificate", due=_due("14/08/2026"),
               by="Sub-registrar, Khammam"),
        _draft("H3", "Hand in the death certificate copy", due=_due("2026-07-30"),
               by="Gram panchayat, Khammam"),
        _draft("H4", "Attend the field verification visit", due=_due("30th September 2026"),
               by="Survey office, Khammam"),
    ))
    st = _states(plan)
    assert [st[i].order for i in ("H1", "H2", "H3", "H4")] == [3, 2, 1, 4]
    assert plan.next_single_action == "Hand in the death certificate copy"


def test_unreadable_date_sorts_last_not_alphabetically():
    plan = build_plan(_case(
        _draft("I1", "Submit the ration card copy", due=_due("as soon as possible")),
        _draft("I2", "Collect the mutation acknowledgement", due=_due("14/08/2026"),
               by="Sub-registrar, Khammam"),
    ))
    st = _states(plan)
    assert st["I2"].order == 1 and st["I1"].order == 2


def test_refused_deadline_never_drives_the_order():
    plan = build_plan(_case(
        _draft("J1", "Submit the mutation application", due=_due("2026-01-01", conf=0.4)),
        _draft("J2", "Collect the encumbrance certificate", due=_due("2026-08-14"),
               by="Sub-registrar, Khammam"),
    ))
    st = _states(plan)
    assert st["J2"].order == 1 and st["J1"].order == 2
    assert any(r.name == "deadline" and r.status == "refused" for r in plan.refusals)


def test_to_iso_formats():
    assert to_iso("Aavedan 14/08/2026 tak jama karein") == "2026-08-14"
    assert to_iso("kindly complete formalities by 01.09.2026") == "2026-09-01"
    assert to_iso("2026-08-14") == "2026-08-14"
    assert to_iso("14 Aug 2026") == "2026-08-14"
    assert to_iso("September 30th, 2026") == "2026-09-30"
    assert to_iso("14/08/26") == "2026-08-14"
    assert to_iso("08/14/2026") == "2026-08-14"      # only day-first reading is valid
    assert to_iso("31/02/2026") is None              # impossible date, never guessed
    assert to_iso("next Tuesday") is None
    assert to_iso(None) is None
