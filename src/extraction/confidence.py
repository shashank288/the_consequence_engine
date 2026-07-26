"""How much do we believe a field we just read off a photograph?

THE HONEST PROBLEM: nothing in the Sarvam Document Intelligence documentation
promises a per-region confidence score, and M0 could not verify one exists (no
API key). The refusal policy — the spine of this product — cannot depend on a
number that may never arrive. So:

  * if the API DOES return a confidence for the region, we use it, and say so;
  * otherwise we earn a number from evidence that is actually on the page, and
    we never award certainty. The ceiling is 0.95: we did not see the paper.

The evidence is deliberately dumb and inspectable:

  base 0.35            we read *something*, and nothing more is known
  + 0.35  the value has the SHAPE this field takes (a date parses; an area is
          "<n> एकड़ <n> गुंठा"; a survey number is "SN-142/2"; a name is 1-3
          word-tokens). Shape is the strongest cheap signal that OCR did not
          mangle the cell — the stamped-over area cells fail exactly here.
  + 0.15  the value appears verbatim in the page text we were handed
  + 0.05  and appears more than once (the page corroborates itself)
  - 0.10  the field HAS a known shape and this value does not match it
  - 0.25  OCR-noise markers in the value (?, _, replacement chars, run-on
          punctuation, stray combining marks)
  - 0.20  a date whose day/month order is genuinely ambiguous (05/06/2026)

Tuned against config.REFUSE_BELOW (0.75): a clean, well-shaped, verbatim value
lands at 0.85 and is READ; anything shape-broken lands at 0.40 and is REFUSED.
That is the intended asymmetry — being wrong about a plot number is what gets a
farmer's application rejected, so the tie goes to the human.

Owned by feat/extraction. Pure logic, no network — unit-testable, and it is
what makes the demo's refusal reproducible rather than model-luck.
"""
from __future__ import annotations

import re
from typing import NamedTuple

from ..sequencer.dates import to_iso


class Score(NamedTuple):
    """`penalties` is what the escalation queue shows: the reason a field was
    refused is never "it appears on the page", it is whatever docked the marks."""
    value: float
    reasons: list[str]
    penalties: list[str]

    @property
    def decisive(self) -> str:
        return self.penalties[0] if self.penalties else self.reasons[-1]

CEILING = 0.95          # we never saw the paper; certainty is not available
FLOOR = 0.05

BASE = 0.35
SHAPE_MATCH = 0.35
SHAPE_MISS = -0.10
VERBATIM = 0.15
CORROBORATED = 0.05
GARBLE = -0.25
# Small on purpose. "01.09.2026" is day-first on an Indian form, and
# sequencer/dates.py already commits to that reading — so this is a recorded
# assumption, not a coin flip. Docking it to a refusal would refuse most dates
# on most of these papers and make the refusal signal meaningless. The headline
# refusal in this product is a cell nobody can read, not a convention.
AMBIGUOUS_DATE = -0.05

# Devanagari digits appear on these pages beside Latin ones, often in one cell.
_D = r"[0-9०-९]"
# Letters only — the Devanagari digit block (U+0966-U+096F) is carved out, so a
# numeric cell can never pass as a name.
_WORD = r"[A-Za-zऀ-॥॰-ॿ]"

_ACRE = r"(?:एकड़|एकड|एकर|acres?|ac\.?)"
_GUNTA = r"(?:गुंठा|गुंटा|गुन्ठा|gunthas?|guntas?)"
_HECTARE = r"(?:हेक्टर|हेक्टेयर|hectares?|ha\.?)"

SHAPES: dict[str, re.Pattern] = {
    # "२ एकड़ १३ गुंठा" / "1 acre 05 gunta" / "0.8 hectare"
    "plot_area": re.compile(
        rf"^{_D}+(?:[.,]{_D}+)?\s*(?:{_ACRE}|{_HECTARE})"
        rf"(?:\s*{_D}+\s*{_GUNTA})?$"),
    # "SN-142/2", "SN 143", "142/2"
    "survey_no": re.compile(rf"^(?:[A-Za-z]{{1,4}}[-\s]?)?{_D}+(?:/{_D}+)?$"),
    "plot_no": re.compile(rf"^(?:[A-Za-z]{{1,4}}[-\s]?)?{_D}+(?:/{_D}+)?$"),
    "khata_no": re.compile(rf"^{_D}+$"),
    # a person: 1-3 word tokens, optional initial-dot. Four tokens is how the
    # struck-through-and-rewritten owner cell announces itself.
    "owner_name": re.compile(rf"^{_WORD}{{2,}}\.?(?:\s+{_WORD}{{1,}}\.?){{0,2}}$"),
    "father_name": re.compile(rf"^{_WORD}{{2,}}\.?(?:\s+{_WORD}{{1,}}\.?){{0,2}}$"),
    "amount": re.compile(rf"^(?:₹|Rs\.?|INR)?\s*{_D}+(?:[,\s]{_D}{{2,3}})*(?:\.{_D}{{1,2}})?$",
                         re.IGNORECASE),
}
NAME_LIKE = {"owner_name", "father_name"}

_GARBLE_CHARS = re.compile(r"[?_�▨□░-▓]")
_RUN_ON_PUNCT = re.compile(r"[.\-–—/\\|]{3,}")
_STRAY_MATRA = re.compile(r"(?:^|\s)[ऀ-ःऺ-ॏ॑-ॗ]")
# both components <= 12, so day-first vs month-first cannot be decided
_AMBIGUOUS_NUMERIC_DATE = re.compile(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})\b")


def _shape_verdict(field: str, value: str) -> tuple[float, str] | None:
    """(delta, reason) or None when this field has no known shape."""
    if field in ("deadline", "date", "due"):
        return ((SHAPE_MATCH, "parses as a calendar date") if to_iso(value)
                else (SHAPE_MISS, "does not parse as a date"))
    pattern = SHAPES.get(field)
    if pattern is None:
        return None
    if pattern.match(value.strip()):
        return SHAPE_MATCH, "matches the shape this field takes on these pages"
    if field in NAME_LIKE and len(value.split()) > 3:
        return SHAPE_MISS, ("cell holds more words than one name — an overwritten "
                            "or struck-through entry reads like this")
    return SHAPE_MISS, "does not match the shape this field takes on these pages"


def _occurrences(value: str, page_text: str) -> int:
    """Token-bounded count. A plain substring count lets "रामय्या" be
    "corroborated" by a different row's "रामय्या स." — that is not a second
    sighting of the same field, it is a different cell."""
    rx = re.compile(rf"(?<![A-Za-zऀ-ॿ0-9]){re.escape(value)}(?![A-Za-zऀ-ॿ0-9])")
    return len(rx.findall(page_text))


def score(field: str, value: str, page_text: str = "",
          api_confidence: float | None = None) -> Score:
    """Reasons are user-facing: they are what the escalation queue shows a human
    next to the crop."""
    if api_confidence is not None:
        return Score(max(FLOOR, min(CEILING, float(api_confidence))),
                     ["confidence reported by Doc-Intelligence for this region"], [])

    value = (value or "").strip()
    if not value:
        return Score(FLOOR, ["nothing was read for this field"],
                     ["nothing was read for this field"])

    conf = BASE
    reasons = ["no per-region confidence returned by the API — "
               "scored from evidence on the page"]
    penalties: list[str] = []

    def award(delta: float, why: str) -> None:
        nonlocal conf
        conf += delta
        reasons.append(why)
        if delta < 0:
            penalties.append(why)

    verdict = _shape_verdict(field, value)
    if verdict is not None:
        award(*verdict)

    if page_text:
        occurrences = _occurrences(value, page_text)
        if occurrences >= 1:
            award(VERBATIM, "appears verbatim in the extracted page text")
        else:
            # Scored anyway (the caller may be checking a model's proposal), but
            # a value we cannot find on the page earns nothing for being there.
            award(0.0, "not found as a standalone value in the page text")
        # Short values collide by accident; only a substantial repeat is evidence.
        if occurrences >= 2 and len(value) >= 4:
            award(CORROBORATED, "the page repeats this value elsewhere")

    if _GARBLE_CHARS.search(value) or _RUN_ON_PUNCT.search(value) or _STRAY_MATRA.search(value):
        award(GARBLE, "carries OCR-noise characters")

    if field in ("deadline", "date", "due"):
        m = _AMBIGUOUS_NUMERIC_DATE.search(value)
        if m and int(m.group(1)) <= 12 and int(m.group(2)) <= 12:
            award(AMBIGUOUS_DATE,
                  f"read day-first per Indian convention — '{m.group(0)}' could "
                  "also be month-first")

    return Score(max(FLOOR, min(CEILING, round(conf, 3))), reasons, penalties)
