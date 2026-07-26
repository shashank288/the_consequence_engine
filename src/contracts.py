"""Shared data contracts for The Consequence Engine.

FROZEN CONTRACT: every branch codes against these models. Changing this file
requires a PR to main labeled CONTRACT-CHANGE plus a row in IDEA_SCOPE.md §16.
Pure pydantic — no I/O, no Sarvam calls here.
"""
from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field


class SourceRef(BaseModel):
    """Where on which page a claim rests. Everything user-visible must carry one."""
    doc_id: str
    page: int = 1
    quote: Optional[str] = None            # exact words on the page
    bbox: Optional[list[float]] = None     # [x0,y0,x1,y1] normalised 0-1 if known
    crop_path: Optional[str] = None        # cropped field image for escalation view


class FieldReading(BaseModel):
    """One consequence-bearing field read off a document."""
    name: str                              # "deadline" | "amount" | "owner_name" | "plot_no" | ...
    value: Optional[str] = None            # None when refused/absent
    confidence: float = 0.0
    status: Literal["read", "refused", "absent"] = "absent"
    source: Optional[SourceRef] = None


class Requirement(BaseModel):
    """A precondition THIS document states, with the words that state it."""
    key: str                               # machine key, e.g. "record_name_matches_id"
    quote: str
    source: SourceRef


class ObligationDraft(BaseModel):
    """Normalised obligation: what is asked, by whom, by when, needing what.
    Produced by feat/extraction (LLM+DocAI) or loaded from fixtures."""
    id: str
    doc_id: str
    doc_type: str                          # "mutation_register_page" | "bank_letter" | "sms_screenshot" | ...
    asked_what: str
    asked_by: str
    due: Optional[FieldReading] = None
    amount: Optional[FieldReading] = None
    needs: list[Requirement] = Field(default_factory=list)
    provides: list[str] = Field(default_factory=list)   # keys satisfied once DONE
    identity_fields: list[FieldReading] = Field(default_factory=list)
    unknown: bool = False                  # classifier could not type this item
    raw_excerpt: str = ""


class Mismatch(BaseModel):
    """Same identity field read differently across documents (card 17)."""
    field_name: str
    readings: list[FieldReading]
    classification: Literal["cosmetic", "blocking", "unknown"]
    reason: str


class BlockingEdge(BaseModel):
    """Obligation A cannot start until B completes — with quotable evidence."""
    blocked_id: str
    blocker_id: str
    need_key: str
    reason: str                            # one printable sentence
    evidence: list[SourceRef] = Field(default_factory=list)


class PlanItem(BaseModel):
    obligation_id: str
    state: Literal["actionable", "blocked", "done", "unknown", "duplicate"]
    order: Optional[int] = None            # only for actionable
    duplicate_of: Optional[str] = None
    next_action: Optional[str] = None
    needs_docs: list[str] = Field(default_factory=list)


class Plan(BaseModel):
    case_id: str
    items: list[PlanItem]
    edges: list[BlockingEdge]
    mismatches: list[Mismatch] = Field(default_factory=list)
    refusals: list[FieldReading] = Field(default_factory=list)
    next_single_action: Optional[str] = None


class Correction(BaseModel):
    """A user correction; must propagate everywhere the old value was used."""
    doc_id: str
    field_name: str
    old: Optional[str]
    new: str
    propagated_to: list[str] = Field(default_factory=list)


class Case(BaseModel):
    """Persistence root — Memory L4 lives here."""
    id: str
    drafts: list[ObligationDraft] = Field(default_factory=list)
    provided_facts: list[str] = Field(default_factory=list)  # satisfied by a doc's presence
    done_keys: list[str] = Field(default_factory=list)       # mock status-lookup results
    corrections: list[Correction] = Field(default_factory=list)
    plan: Optional[Plan] = None
