"""Normalisation prompt: extracted page text -> one obligation, in JSON.

The model is allowed to do exactly one thing here — say what THIS page asks for,
in the page's own words. It may not know anything. Every constraint below exists
because breaking it destroys a specific rubric claim:

  * quotes must be verbatim          -> Creativity: every blocking edge quotes
                                        the line it rests on (IDEA_SCOPE.md §4)
  * no invented due/amount           -> Document Intelligence: controlled
                                        uncertainty, never a silent guess
  * no law, no procedure, no deadline it did not read
                                     -> IDEA_SCOPE.md §12 non-goal 1, binding
  * no confidence numbers from the model
                                     -> confidence.py earns those from evidence;
                                        a model's self-reported certainty is not
                                        evidence about a photograph

Anything the model returns is treated as a PROPOSAL. pipeline.py verifies every
quote against the page text and drops what it cannot find. Owned by feat/extraction.
"""
from __future__ import annotations

import json

# Canonical requirement keys. The sequencer matches `needs` to `provides` by
# exact string, so this vocabulary is the joint between documents — a free-text
# key would silently never match and the plan would under-block.
REQUIREMENT_KEYS = {
    "death_certificate": "proof that the recorded owner has died",
    "heirship_certificate": "legal-heir / succession certificate or notarised affidavit",
    "record_name_matches_id": "the name in the record of rights must match the applicant's ID",
    "record_owner_resolved": "the record's owner entry must be unambiguous (no struck-through/overwritten name)",
    "mutation_completed": "the mutation must already be recorded",
    "identity_proof": "an identity document for the applicant",
    "application_fee_paid": "the stated fee must be paid",
    "prior_order": "a court or revenue order referenced by the page",
}

DOC_TYPES = [
    "mutation_register_page",   # record of rights / khatauni / 7-12 extract
    "counter_slip",             # tehsil counter checklist
    "bank_letter",
    "sms_screenshot",
    "death_certificate",
    "identity_document",
    "unknown",                  # ALWAYS available — never force a type
]

SYSTEM = """You normalise ONE photographed Indian land-records document into JSON.

You are reading OCR output from a degraded photograph. It will contain errors.

ABSOLUTE RULES — breaking any of these makes your answer useless:
1. Every "quote" MUST be a character-for-character substring of the page text
   you were given. Do not tidy spelling, spacing, script or punctuation. If you
   cannot find the words, omit the whole item.
2. NEVER state a legal rule, a procedure, a fee, a processing time or a deadline
   that is not written on this page. You have no knowledge of Indian land law
   and must not act as if you do.
3. NEVER invent or infer a date or an amount. If the page does not state one,
   return null. A plausible guess is the worst possible answer.
4. Do not report confidence, certainty or probability. You are not asked.
5. If you cannot tell what kind of document this is, set "doc_type": "unknown"
   and "unknown": true. That is a correct answer, not a failure.
6. Copy values exactly as written, in the page's own script. Do not transliterate
   Devanagari to Latin, and do not translate names.

Return a single JSON object, nothing else."""


def _schema_block() -> str:
    keys = "\n".join(f'    "{k}" — {v}' for k, v in REQUIREMENT_KEYS.items())
    return f"""Return exactly this shape:

{{
  "doc_type": one of {json.dumps(DOC_TYPES, ensure_ascii=False)},
  "unknown": true|false,
  "asked_what": "one sentence: what this page asks the reader to DO. If the page
                 asks for nothing (it is a record, not a demand), describe what
                 must be resolved about it, in the page's own terms.",
  "asked_by": "the office/person named on the page, or \\"not stated on page\\"",
  "due": {{"value_on_page": "the date exactly as printed" | null,
          "quote": "the full line containing it" | null}},
  "amount": {{"value_on_page": "..." | null, "quote": "..." | null}},
  "requirements": [
    {{"key": one of the keys below, "quote": "the verbatim line that states it"}}
  ],
  "identity_fields": [
    {{"name": "owner_name"|"father_name"|"survey_no"|"plot_no"|"plot_area"|"khata_no",
      "value": "exactly as written on the page",
      "quote": "the verbatim line or cell it came from"}}
  ]
}}

Requirement keys (use ONLY these; drop anything that fits none of them):
{keys}"""


def build_messages(page_text: str, *, doc_hint: str = "") -> list[dict]:
    hint = f"\nFilename hint (may be wrong, ignore if it contradicts the page): {doc_hint}\n" if doc_hint else ""
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": (
            f"{_schema_block()}\n{hint}\n"
            "--- PAGE TEXT AS EXTRACTED (errors and all) ---\n"
            f"{page_text}\n"
            "--- END PAGE TEXT ---\n\n"
            "Emit the JSON object now. Every quote must be findable in the text above.")},
    ]
