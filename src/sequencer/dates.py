"""Date normalisation for plan ordering. Pure logic — no I/O, no network.

Real extraction hands us whatever the page said: "14/08/2026", "01.09.2026",
"14 Aug 2026", "2026-08-14", "by 30th September 2026". Ordering must compare
ISO strings; comparing raw page text sorts alphabetically, which is silently
wrong ("01.09.2026" sorts before "14/08/2026"). Anything we cannot read as a
date is UNDATED — it sorts last and is never guessed into an order.
"""
from __future__ import annotations

import datetime
import re

UNDATED = "9999-12-31"          # sorts last; means "no readable deadline"

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}

# YYYY-MM-DD / YYYY.MM.DD / YYYY/MM/DD  (unambiguous, year first)
_ISO = re.compile(r"\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b")
# DD/MM/YYYY and friends — day-first is the Indian convention on these papers
_NUMERIC = re.compile(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})\b")
# 14 Aug 2026 / 30th September, 2026
_DAY_MONTH = re.compile(
    r"\b(\d{1,2})\s*(?:st|nd|rd|th)?[\s,.-]+([A-Za-z]{3,9})\.?[\s,.-]+(\d{2,4})\b")
# Aug 14 2026 / September 30th, 2026
_MONTH_DAY = re.compile(
    r"\b([A-Za-z]{3,9})\.?[\s,.-]+(\d{1,2})\s*(?:st|nd|rd|th)?[\s,.-]+(\d{2,4})\b")


def _year(y: int) -> int:
    """Two-digit years on these papers mean this century ('26' -> 2026)."""
    return y if y >= 100 else 2000 + y


def _build(y: int, m: int, d: int) -> str | None:
    try:
        return datetime.date(_year(y), m, d).isoformat()
    except ValueError:            # 31/02, month 13, ...
        return None


def to_iso(value: str | None) -> str | None:
    """Best-effort ISO-8601 date found in `value`.

    Returns None when the text cannot be read as a date — callers must treat
    that as UNDATED rather than sorting on the raw text.
    """
    if not value:
        return None
    text = value.strip()

    m = _ISO.search(text)
    if m:
        return _build(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    m = _NUMERIC.search(text)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if a > 12 and b <= 12:
            return _build(y, b, a)          # 14/08 -> day first, certain
        if b > 12 and a <= 12:
            return _build(y, a, b)          # 08/14 -> month first, certain
        return _build(y, b, a)              # ambiguous -> day first (Indian)

    for rx, order in ((_DAY_MONTH, "dmy"), (_MONTH_DAY, "mdy")):
        m = rx.search(text)
        if not m:
            continue
        day, name, year = ((m.group(1), m.group(2), m.group(3)) if order == "dmy"
                           else (m.group(2), m.group(1), m.group(3)))
        month = _MONTHS.get(name[:3].lower())
        if month:
            return _build(int(year), month, int(day))
    return None


def due_iso(reading) -> str:
    """Sort key for a due FieldReading: ISO date, or UNDATED when unreadable.

    A refused reading has no value by construction, so it lands in UNDATED —
    a field we refused to read can never silently drive the ordering.
    """
    if reading is None or reading.status != "read":
        return UNDATED
    return to_iso(reading.value) or UNDATED
