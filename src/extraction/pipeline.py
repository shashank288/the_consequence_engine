"""Photographed page -> ObligationDraft. The M1 critical path.

    extract_drafts(["fixtures/private/register_page.png"]) -> list[ObligationDraft]

Three stages, in this order on purpose:

  1. Doc-Intelligence gives us page text (shape undocumented — `_pages` is
     deliberately paranoid about what the result file looks like).
  2. A DETERMINISTIC reader parses what it can prove: markdown table rows,
     requirement lines, a deadline line. It is the floor, and it is what runs
     when there is no API key.
  3. sarvam-105b (prompts.py) proposes the rest as prose. Every proposal is then
     put through the SAME gate as stage 2 — quote must be findable on the page,
     confidence must be earned by confidence.py.

The model never gets the last word. It cannot introduce a requirement whose
words are not on the page, it cannot set its own confidence, and it cannot
supply a date the page does not carry. That is what makes a blocking edge in the
plan defensible when a judge asks "where does that come from?" — and it is why
the LLM being flaky (risk register, IDEA_SCOPE.md §11) degrades the output
instead of corrupting it.

Owned by feat/extraction.
"""
from __future__ import annotations

import pathlib
import re

from ..config import REFUSE_BELOW
from ..contracts import FieldReading, ObligationDraft, Requirement, SourceRef
from ..sarvam_client import SarvamUnavailable, chat_json, doc_intelligence_extract, offline_mode
from ..sequencer.dates import to_iso
from . import prompts
from .confidence import score

# --- what a document TYPE means for the plan ---------------------------------
# AUTHORED MAPPING, not an extracted claim: once this kind of document is in
# order, these keys are satisfiable. The *edges* still come from the other
# pages' own words — a slip that never says "must match the record" produces no
# edge to the register page, no matter what this table says.
DOC_TYPE_PROVIDES: dict[str, list[str]] = {
    "mutation_register_page": ["record_owner_resolved", "record_name_matches_id"],
    "counter_slip": ["mutation_completed"],
    "bank_letter": ["bank_succession_done"],
    "death_certificate": ["death_certificate"],
    "identity_document": ["identity_proof"],
}

# doc_type -> (marker, ...). First type with a marker present on the page wins;
# the marker that matched is kept as the classification's evidence.
DOC_TYPE_MARKERS: list[tuple[str, tuple[str, ...]]] = [
    # NB: no bare "record of rights" here — a bank letter demanding one would
    # then classify as the register page itself. Markers must name the document,
    # not its subject matter.
    ("mutation_register_page", ("अधिकार अभिलेख", "ग्राम नमूना", "खतौनी", "खाता",
                                "7/12", "७/१२", "जमाबंदी", "क्षेत्रफल")),
    ("counter_slip", ("चेकलिस्ट", "checklist", "तहसील कार्यालय", "तलाठी",
                      "talathi", "म्यूटेशन", "फेरफार", "mutation application")),
    ("bank_letter", ("bank", "बैंक", "branch manager", "शाखा", "succession claim",
                     "खाता क्रमांक", "account holder")),
    ("death_certificate", ("death certificate", "मृत्यु प्रमाण पत्र", "form no. 6")),
    ("sms_screenshot", ("sms", "dear customer", "vm-", "inbox")),
    ("identity_document", ("aadhaar", "आधार", "pan card", "voter id")),
]

# A line only states a requirement if it says so. Without one of these the line
# is prose and we do not turn it into a dependency.
REQUIREMENT_MARKERS = ("required", "must ", "shall ", "mandatory", "needs to",
                       "आवश्यक", "अनिवार्य", "चाहिए", "जमा कर", "आवश्यकता",
                       "प्रस्तुत कर", "सादर कर")
REQUIREMENT_KEY_MARKERS: list[tuple[str, tuple[str, ...]]] = [
    ("death_certificate", ("death certificate", "मृत्यु प्रमाण")),
    ("heirship_certificate", ("heirship", "legal heir", "वारसाहक्क", "वारिस",
                              "उत्तराधिकार", "affidavit", "शपथपत्र", "शपथ पत्र")),
    ("record_name_matches_id", ("match the record", "record-of-rights entry exactly",
                                "matches the record", "नाम मेल", "नाम समान")),
    ("mutation_completed", ("updated record of rights", "mutation is complete",
                            "फेरफार पूर्ण", "अद्यतन अधिकार अभिलेख")),
    ("prior_order", ("order of", "आदेश की प्रति", "revenue order")),
    ("identity_proof", ("identity proof", "पहचान प्रमाण", "aadhaar", "आधार")),
    ("application_fee_paid", ("fee", "शुल्क")),
]

# A date is only a DEADLINE if the page frames it as one. Otherwise it is just a
# date on a page (an issue date, a mutation reference) and inventing a deadline
# out of it is exactly the failure mode this product exists to avoid.
DEADLINE_MARKERS = ("तक", "by ", "before ", "due", "last date", "अंतिम तिथि",
                    "अंतिम दिनांक", "on or before", "within", "के भीतर")

# Devanagari/English column headers -> our field names.
COLUMN_FIELDS: list[tuple[str, tuple[str, ...]]] = [
    ("khata_no", ("खाता", "khata")),
    ("survey_no", ("सर्वे", "survey", "s. no", "gat")),
    ("owner_name", ("मालिक", "owner", "कब्जेदार", "holder")),
    ("father_name", ("पिता", "father")),
    ("plot_area", ("क्षेत्रफल", "area", "क्षेत्र")),
    ("mutation_ref", ("फेरफार", "mutation")),
]
ORG_MARKERS = ("कार्यालय", "तहसील", "तलाठी", "bank", "बैंक", "branch", "शाखा",
               "office", "department", "विभाग", "corporation", "नगर")

NOT_STATED = "not stated on page"

# Field names are machine keys; a refusal shown to a farmer at a tehsil counter
# should name the column they have to re-photograph, in the script it is in.
FIELD_LABELS = {
    "owner_name": "owner name (मालिक का नाम)",
    "father_name": "father's name (पिता का नाम)",
    "plot_area": "area (क्षेत्रफल)",
    "survey_no": "survey number (सर्वे नं.)",
    "khata_no": "khata number (खाता)",
    "deadline": "deadline",
    "amount": "amount",
}


def label(field: str) -> str:
    return FIELD_LABELS.get(field, field.replace("_", " "))


# --- 1. raw Doc-Intelligence result -> page text ------------------------------

class Page:
    """One page of one document, plus any region-level detail we were given."""

    def __init__(self, doc_id: str, number: int, text: str, blocks: list[dict] | None = None):
        self.doc_id, self.number, self.text = doc_id, number, text
        self.blocks = blocks or []

    def api_confidence(self, value: str) -> float | None:
        """If the API happened to score the region this value came from, use it.
        Nothing in the docs promises this exists — hence the None path."""
        for b in self.blocks:
            btext = str(b.get("text") or b.get("content") or "")
            if value and value in btext:
                for k in ("confidence", "score", "conf"):
                    if isinstance(b.get(k), (int, float)):
                        return float(b[k])
        return None

    def bbox(self, value: str) -> list[float] | None:
        for b in self.blocks:
            btext = str(b.get("text") or b.get("content") or "")
            if value and value in btext:
                for k in ("bbox", "bounding_box", "box"):
                    box = b.get(k)
                    if isinstance(box, list) and len(box) == 4:
                        return [float(v) for v in box]
        return None


_TEXT_KEYS = ("text", "markdown", "md", "content", "html", "plain_text")


def _text_of(obj) -> str:
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        for k in _TEXT_KEYS:
            v = obj.get(k)
            if isinstance(v, str) and v.strip():
                return v
    return ""


def _pages(payload: dict, doc_id: str) -> list[Page]:
    """The download result's shape is undocumented, so accept the plausible
    ones: a bare string, {text|markdown|...}, or {pages: [...]} of either."""
    out: list[Page] = []
    for doc in payload.get("documents") or []:
        content = doc.get("content")
        raw_pages = content.get("pages") if isinstance(content, dict) else None
        if isinstance(raw_pages, list) and raw_pages:
            for i, p in enumerate(raw_pages, start=1):
                number, blocks = i, None
                if isinstance(p, dict):
                    number = int(p.get("page_number") or p.get("page") or i)
                    for k in ("blocks", "regions", "lines", "words", "elements"):
                        if isinstance(p.get(k), list):
                            blocks = p[k]
                            break
                out.append(Page(doc_id, number, _text_of(p), blocks))
        else:
            out.append(Page(doc_id, len(out) + 1, _text_of(content)))
    return [p for p in out if p.text.strip()] or out


# --- 2. the gate: a quote must be on the page ---------------------------------

def _verify_quote(quote: str | None, text: str) -> str | None:
    """Return the page's OWN words for `quote`, or None.

    Whitespace may differ (the model reflows, the table pipes get eaten), so we
    match token-by-token and hand back the span as the PAGE spells it — never
    the model's tidied-up version.
    """
    if not quote or not quote.strip():
        return None
    tokens = quote.split()
    if not tokens:
        return None
    m = re.compile(r"\s+".join(map(re.escape, tokens))).search(text)
    return m.group(0) if m else None


def _reading(name: str, value: str | None, page: Page, quote: str | None,
             notes: list[str], page_value: str | None = None) -> FieldReading:
    """One field, scored honestly and refused if it does not clear the bar.

    A refused reading keeps its SourceRef: value=None, but the human reviewer
    (and feat/register's crop view) still gets the exact words on the page.
    `notes` collects the why — the FROZEN contract has no field for it, so it
    is surfaced through the draft's raw_excerpt. Passed in rather than held
    module-level: two uploads can be in flight at once.

    `page_value` is the text AS PRINTED when `value` has been normalised (a date
    stored as 2026-08-14 that the page writes as 14/08/2026). Evidence is always
    weighed against what the page actually says — scoring the normalised form
    would find it nowhere on the page and refuse every date we understood.
    """
    if not value or not value.strip():
        return FieldReading(name=name, value=None, confidence=0.0, status="absent")
    value = value.strip()
    evidence = (page_value or value).strip()
    verified = _verify_quote(quote, page.text) or _verify_quote(evidence, page.text)
    scored = score(name, evidence, page.text, page.api_confidence(evidence))
    source = SourceRef(doc_id=page.doc_id, page=page.number, quote=verified,
                       bbox=page.bbox(evidence))
    if verified is None:
        # We could not find these words on the page we were handed. That is not
        # a reading, it is a claim about a page — refuse it.
        notes.append(f"{label(name)}: words not found on the page")
        return FieldReading(name=name, value=None, confidence=min(scored.value, 0.2),
                            status="refused", source=source)
    if scored.value < REFUSE_BELOW:
        notes.append(f"{label(name)} ({scored.value:.2f}) — {scored.decisive}")
        return FieldReading(name=name, value=None, confidence=scored.value,
                            status="refused", source=source)
    for assumption in scored.penalties:
        # Read, but not for free: an assumption we made is stated, not buried.
        notes.append(f"{label(name)} read at {scored.value:.2f} — {assumption}")
    return FieldReading(name=name, value=value, confidence=scored.value,
                        status="read", source=source)


# --- 3. deterministic reading -------------------------------------------------

def _lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def _classify(text: str) -> tuple[str, str | None]:
    """Most markers wins, ties broken by table order. Counting beats
    first-match: single shared words ("खाता" on a bank statement, "फेरफार" as a
    column header) otherwise decide the type on their own."""
    low = text.lower()
    best_type, best_hits = "unknown", []
    for doc_type, markers in DOC_TYPE_MARKERS:
        hits = [m for m in markers if m.lower() in low]
        if len(hits) > len(best_hits):
            best_type, best_hits = doc_type, hits
    return best_type, ", ".join(best_hits) if best_hits else None


def _issuer(text: str) -> str:
    for ln in _lines(text):
        low = ln.lower()
        if any(m.lower() in low for m in ORG_MARKERS):
            return ln.strip("#[]| ").strip()
    return NOT_STATED


# The date exactly as printed, so confidence is weighed against the page's own
# characters rather than against our normalised ISO form.
_DATE_TOKEN = re.compile(
    r"\d{1,4}[-/.]\d{1,2}[-/.]\d{2,4}"
    r"|\d{1,2}\s*(?:st|nd|rd|th)?[\s,.-]+[A-Za-z]{3,9}\.?[\s,.-]+\d{2,4}")


def _deadline_line(text: str) -> tuple[str, str, str] | None:
    """(iso_date, verbatim_line, date_as_printed) for the first line the page
    frames as a due date. No marker, no deadline — we do not promote a stray
    date: an issue date or a mutation reference is not something to act by."""
    for ln in _lines(text):
        low = ln.lower()
        if not any(m.lower() in low for m in DEADLINE_MARKERS):
            continue
        iso = to_iso(ln)
        if iso:
            m = _DATE_TOKEN.search(ln)
            return iso, ln, (m.group(0) if m else ln)
    return None


def _requirements(text: str, page: Page) -> list[Requirement]:
    found: dict[str, Requirement] = {}
    for ln in _lines(text):
        low = ln.lower()
        if not any(m.lower() in low for m in REQUIREMENT_MARKERS):
            continue
        for key, markers in REQUIREMENT_KEY_MARKERS:
            if key in found or not any(m.lower() in low for m in markers):
                continue
            quote = _verify_quote(ln, page.text)
            if quote:                          # no quote -> no requirement. Ever.
                found[key] = Requirement(
                    key=key, quote=quote,
                    source=SourceRef(doc_id=page.doc_id, page=page.number, quote=quote))
            # deliberately no break: "an attested copy of the updated record of
            # rights is required along with the death certificate" states TWO
            # requirements, and dropping either would under-block the plan.
    return list(found.values())


def _table_rows(text: str) -> list[dict[str, str]]:
    """Markdown-ish table -> [{field: cell}]. Returns [] when there is no table
    we can read; we do not try to infer columns from whitespace."""
    header: dict[int, str] | None = None
    rows: list[dict[str, str]] = []
    for ln in _lines(text):
        if ln.count("|") < 2:
            continue
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if set("".join(cells)) <= set("-: "):          # separator row
            continue
        if header is None:
            mapping: dict[int, str] = {}
            for i, c in enumerate(cells):
                low = c.lower()
                for field, markers in COLUMN_FIELDS:
                    if any(m.lower() in low for m in markers):
                        mapping[i] = field
                        break
            if len(mapping) >= 3:                      # a real header, not data
                header = mapping
            continue
        rows.append({header[i]: c for i, c in enumerate(cells)
                     if i in header and c})
    return [r for r in rows if r]


def _amended_row(rows: list[dict[str, str]]) -> tuple[dict[str, str] | None, str]:
    """Which row is this case about? Only the page may answer.

    A register page photographed for a mutation is photographed for the row that
    was amended — and an amended owner cell announces itself by holding more
    than one name. If nothing marks a row, we say so instead of picking one.
    """
    if len(rows) == 1:
        return rows[0], "the page carries a single record row"
    # An Indian personal name in these columns runs 1-3 tokens. Four or more in
    # one owner cell means the cell holds two names — i.e. a correction.
    amended = [r for r in rows if len((r.get("owner_name") or "").split()) > 3]
    if len(amended) == 1:
        return amended[0], ("the only row whose owner cell holds more than one "
                            "name — an overwritten or struck-through entry")
    return None, (f"the page carries {len(rows)} record rows and none is marked "
                  "as amended, so which row this case concerns cannot be read "
                  "off the page")


# --- 4. LLM proposals, put through the same gate ------------------------------

def _llm_proposal(page: Page, doc_hint: str) -> tuple[dict, str]:
    """-> (proposal, note). Never raises: a flaky model must degrade the draft,
    not break the run (IDEA_SCOPE.md §11)."""
    if offline_mode():
        return {}, "offline: deterministic reader only, no normalisation model"
    try:
        return chat_json(prompts.build_messages(page.text, doc_hint=doc_hint)), "sarvam-105b normalisation applied"
    except SarvamUnavailable:
        return {}, "no API key: deterministic reader only"
    except Exception as exc:                      # noqa: BLE001 - demo must survive
        return {}, f"normalisation model unavailable ({type(exc).__name__}); deterministic reader only"


# --- 5. one document -> one draft --------------------------------------------

def _draft_for(page: Page, index: int, provenance: str) -> ObligationDraft:
    notes: list[str] = []
    text = page.text
    doc_type, marker = _classify(text)
    proposal, llm_note = _llm_proposal(page, doc_hint=page.doc_id)

    # The model may name the type only if the deterministic reader could not,
    # and only from the sanctioned vocabulary. It may always say "unknown".
    if doc_type == "unknown":
        proposed = str(proposal.get("doc_type") or "")
        if proposed in prompts.DOC_TYPES:
            doc_type = proposed

    # --- deadline: page-framed date first, model second, invention never
    due = None
    det_deadline = _deadline_line(text)
    if det_deadline:
        iso, line, printed = det_deadline
        due = _reading("deadline", iso, page, line, notes, page_value=printed)
    else:
        p_due = proposal.get("due") or {}
        raw, quote = p_due.get("value_on_page"), p_due.get("quote")
        if raw and _verify_quote(quote or raw, text):
            due = _reading("deadline", to_iso(str(raw)) or str(raw), page,
                           quote or raw, notes)
    if due is None:
        due = FieldReading(name="deadline", value=None, confidence=0.0, status="absent")

    p_amt = proposal.get("amount") or {}
    amount = None
    if p_amt.get("value_on_page") and _verify_quote(p_amt.get("quote"), text):
        amount = _reading("amount", str(p_amt["value_on_page"]), page,
                          p_amt.get("quote"), notes)

    # --- requirements: deterministic first, then any the model can prove
    needs = _requirements(text, page)
    have = {n.key for n in needs}
    for item in proposal.get("requirements") or []:
        key, quote = str(item.get("key") or ""), item.get("quote")
        if key in prompts.REQUIREMENT_KEYS and key not in have:
            verified = _verify_quote(quote, text)
            if verified:
                needs.append(Requirement(key=key, quote=verified,
                                         source=SourceRef(doc_id=page.doc_id,
                                                          page=page.number, quote=verified)))
                have.add(key)

    # --- identity fields: the table is authoritative where there is one
    rows = _table_rows(text)
    row, row_reason = _amended_row(rows)
    identity: list[FieldReading] = []
    if row:
        for field in ("owner_name", "father_name", "survey_no", "plot_area", "khata_no"):
            if row.get(field):
                identity.append(_reading(field, row[field], page, row[field], notes))
    seen = {(f.name, f.value) for f in identity}
    for item in proposal.get("identity_fields") or []:
        name, value = str(item.get("name") or ""), item.get("value")
        if not name or not value or (name, value) in seen:
            continue
        if rows and not row:
            continue                    # unresolved row: the model may not pick one
        if _verify_quote(item.get("quote") or str(value), text):
            identity.append(_reading(name, str(value), page, item.get("quote"), notes))
            seen.add((name, str(value)))

    refused = [label(f.name) for f in [due, amount, *identity]
               if f is not None and f.status == "refused"]
    asked_what, asked_by = _asked(doc_type, text, row, rows, identity, needs,
                                  refused, proposal)

    unknown = doc_type == "unknown"
    excerpt = _excerpt(provenance, llm_note, doc_type, marker, rows,
                       row_reason if rows else "", notes, text)
    return ObligationDraft(
        id=f"O{index}", doc_id=page.doc_id, doc_type=doc_type,
        asked_what=asked_what, asked_by=asked_by, due=due, amount=amount,
        needs=needs, provides=list(DOC_TYPE_PROVIDES.get(doc_type, [])),
        identity_fields=identity, unknown=unknown, raw_excerpt=excerpt)


def _asked(doc_type, text, row, rows, identity, needs, refused, proposal) -> tuple[str, str]:
    """What this page asks for — in the page's terms, never in law's terms."""
    issuer = _issuer(text)
    if doc_type == "unknown":
        return ("Unclassified document — a human must read it before this case "
                "can be sequenced", issuer)

    if doc_type == "mutation_register_page":
        where = ""
        survey = next((f.value for f in identity if f.name == "survey_no" and f.value), None)
        if survey:
            where = f" for {survey}"
        if rows and not row:
            return (f"Identify which of the {len(rows)} record rows on this page "
                    "this case concerns — the page does not mark one", issuer)
        if refused:
            return (f"Get a legible reading of {', '.join(sorted(set(refused)))}"
                    f"{where} on the record of rights — it could not be read "
                    "from this photograph", issuer)
        return (f"Confirm the record-of-rights entry{where} is current before it "
                "is relied on", issuer)

    deadline = _deadline_line(text)
    if deadline:
        # The page's own instruction. Only a leading list marker is stripped —
        # this is a display string; the SourceRef keeps the line verbatim.
        return re.sub(r"^\s*\(?\d{1,2}[.)]\s*", "", deadline[1]), issuer
    proposed = str(proposal.get("asked_what") or "").strip()
    if proposed:
        return proposed, issuer
    if needs:
        return (f"Satisfy the {len(needs)} requirement(s) this page lists", issuer)
    return "Act on this document — it states no deadline of its own", issuer


def _excerpt(provenance, llm_note, doc_type, marker, rows, row_reason, refused, text) -> str:
    bits = [f"[{provenance}] {llm_note}."]
    bits.append(f"Classified {doc_type}" + (f' on "{marker}"' if marker else " — no type marker found") + ".")
    if rows:
        bits.append(f"{len(rows)} table row(s); row chosen: {row_reason}.")
    if refused:
        bits.append("Refused: " + "; ".join(refused) + ".")
    head = " ".join(_lines(text)[:2])[:180]
    bits.append(f"Page begins: {head}")
    return " ".join(bits)


# --- 6. the entry points ------------------------------------------------------

# Documents whose PRESENCE satisfies a requirement — you do not "do" a death
# certificate, you either have it or you do not.
PRESENCE_FACTS = {"death_certificate": "death_certificate",
                  "identity_document": "identity_proof"}


def presence_facts(drafts: list[ObligationDraft]) -> list[str]:
    """Requirement keys already satisfied by what was handed in."""
    return sorted({PRESENCE_FACTS[d.doc_type] for d in drafts
                   if d.doc_type in PRESENCE_FACTS})



def extract_drafts(image_paths: list[str]) -> list[ObligationDraft]:
    """Photographs -> drafts. One draft per document (first page carries it).

    Raises SarvamUnavailable if there is neither a key nor SARVAM_OFFLINE=1 —
    the caller must show that, not a plausible-looking empty plan.
    """
    drafts: list[ObligationDraft] = []
    for i, path in enumerate(image_paths, start=1):
        p = pathlib.Path(path)
        payload = doc_intelligence_extract(str(p))
        pages = _pages(payload, doc_id=p.stem)
        provenance = str(payload.get("provenance", "unknown"))
        if not pages or not pages[0].text.strip():
            drafts.append(ObligationDraft(
                id=f"O{i}", doc_id=p.stem, doc_type="unknown",
                asked_what="Nothing legible was extracted from this photograph — "
                           "re-photograph it or hand it to a human",
                asked_by=NOT_STATED, unknown=True,
                raw_excerpt=f"[{provenance}] Doc-Intelligence returned no text for {p.name}."))
            continue
        drafts.append(_draft_for(pages[0], i, provenance))
    return drafts
