"""Text normalisation for the sequencer. Pure logic — no I/O, no network.

Everything here is script-aware: real extraction returns Devanagari as often as
Latin, and the old ASCII-only normaliser silently erased every Devanagari value
(making two different Hindi names look identical). Nothing in this module may
guess: the cross-script comparison either proves a match or says it cannot tell.
"""
from __future__ import annotations

import unicodedata

# Filler words that carry no identity for an obligation — dropped before the
# similarity comparison so "the/of/at" cannot inflate a duplicate score.
STOPWORDS = {
    "a", "an", "the", "of", "at", "to", "in", "on", "for", "from", "into",
    "and", "or", "is", "are", "be", "by", "with", "this", "that", "so",
    "your", "our", "it", "as", "no", "not", "s", "please", "kindly", "must",
}

# Organisation noise — "Canara Bank" and "Canara Bank Ltd, Khammam Branch"
# are the same asker; the suffixes must not defeat the subset test.
ORG_NOISE = {
    "ltd", "limited", "pvt", "private", "inc", "corp", "corporation",
    "co", "company", "branch", "office", "dept", "department", "centre",
    "center", "counter", "sub", "govt", "government",
}

_UNKNOWN_ASKER = {"", "unknown", "unclear", "not stated", "na", "n a"}

_DEVANAGARI = range(0x0900, 0x0980)


def norm(s: str | None) -> str:
    """Lowercase, drop punctuation/symbols, collapse whitespace.

    Letters, digits and combining marks of ANY script survive — dropping
    Devanagari vowel signs here would corrupt every Hindi reading downstream.
    """
    out = []
    for ch in (s or ""):
        if ch.isspace():
            out.append(" ")
        elif unicodedata.category(ch)[0] in ("L", "N", "M"):
            out.append(ch.lower())
        else:
            out.append(" ")
    return " ".join("".join(out).split())


def _stem(t: str) -> str:
    """Crude plural fold so 'heirs'/'heir' compare equal. Deliberately dumb."""
    return t[:-1] if len(t) > 3 and t.endswith("s") and not t.endswith("ss") else t


def tokens(s: str | None) -> set[str]:
    return set(norm(s).split())


def content_tokens(s: str | None) -> set[str]:
    return {_stem(t) for t in norm(s).split() if t not in STOPWORDS}


def containment(a: str | None, b: str | None) -> float:
    """Share of the SHORTER ask that the longer one also states."""
    ta, tb = content_tokens(a), content_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


def jaccard(a: str | None, b: str | None) -> float:
    """Over-merge guard: containment alone merges a short ask into any longer
    one that happens to repeat its words."""
    ta, tb = content_tokens(a), content_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def office_relation(a: str | None, b: str | None) -> str:
    """'same' | 'different' | 'unknown' for two asker strings.

    'same' is token-subset in either direction after dropping org noise, so
    "Canara Bank" == "Canara Bank Ltd, Khammam Branch" but
    "Tehsil office, Khammam" != "Tehsil office, Warangal".
    """
    if norm(a) in _UNKNOWN_ASKER or norm(b) in _UNKNOWN_ASKER:
        return "unknown"
    ta = {t for t in content_tokens(a) if t not in ORG_NOISE}
    tb = {t for t in content_tokens(b) if t not in ORG_NOISE}
    if not ta or not tb:
        return "unknown"
    if ta <= tb or tb <= ta:
        return "same"
    return "different"


def has_devanagari(s: str | None) -> bool:
    return any(ord(ch) in _DEVANAGARI for ch in (s or ""))


# --- cross-script name comparison -------------------------------------------
# Both sides collapse to a coarse consonant skeleton: aspirates fold onto their
# base, retroflex onto dental, all sibilants onto 's', vowels and 'h' drop.
# A skeleton match across scripts is strong evidence of the same name; a
# non-match proves nothing, so it returns 'unknown', never 'blocking'.

_DEVA_MAP = {
    "क": "k", "ख": "k", "ग": "g", "घ": "g", "ङ": "n",
    "च": "c", "छ": "c", "ज": "j", "झ": "j", "ञ": "n",
    "ट": "t", "ठ": "t", "ड": "d", "ढ": "d", "ण": "n",
    "त": "t", "थ": "t", "द": "d", "ध": "d", "न": "n", "ऩ": "n",
    "प": "p", "फ": "f", "ब": "b", "भ": "b", "म": "m",
    "य": "y", "र": "r", "ऱ": "r", "ल": "l", "ळ": "l", "व": "v",
    "श": "s", "ष": "s", "स": "s", "ह": "",
    "क़": "k", "ख़": "k", "ग़": "g", "ज़": "j", "ड़": "r", "ढ़": "r", "फ़": "f",
    "ं": "n", "ँ": "n",           # anusvara / candrabindu read as a nasal
}

_LATIN_DIGRAPHS = (("chh", "c"), ("sh", "s"), ("ch", "c"), ("kh", "k"),
                   ("gh", "g"), ("jh", "j"), ("th", "t"), ("dh", "d"),
                   ("ph", "f"), ("bh", "b"), ("zh", "j"))
_LATIN_FOLD = {"w": "v", "q": "k", "z": "j", "x": "k"}


def _deva_skeleton(s: str) -> str:
    out = []
    for ch in unicodedata.normalize("NFC", s):
        if ch.isspace():
            out.append(" ")
        elif ch in _DEVA_MAP:
            out.append(_DEVA_MAP[ch])
        # matras, independent vowels, virama, nukta, danda: dropped
    return " ".join("".join(out).split())


def _latin_skeleton(s: str) -> str:
    t = norm(s)
    for a, b in _LATIN_DIGRAPHS:
        t = t.replace(a, b)
    out = []
    for ch in t:
        if ch.isspace():
            out.append(" ")
        elif ch in "aeiouh" or not ch.isalpha():
            continue
        else:
            out.append(_LATIN_FOLD.get(ch, ch))
    return " ".join("".join(out).split())


def skeleton(s: str | None) -> str:
    s = s or ""
    return _deva_skeleton(s) if has_devanagari(s) else _latin_skeleton(s)


def cross_script_verdict(a: str, b: str) -> tuple[str, str]:
    """Compare a Devanagari reading with a Latin one. Never returns 'cosmetic'
    on a guess: only an exact, long-enough skeleton match counts as proof."""
    sa, sb = skeleton(a), skeleton(b)
    if sa and sa == sb and len(sa.replace(" ", "")) >= 3:
        return ("cosmetic",
                f"same name written in two scripts — consonant skeleton '{sa}' "
                f"matches across Devanagari and Latin")
    return ("unknown",
            "readings are in different scripts and their consonant skeletons "
            f"differ ('{sa or '-'}' vs '{sb or '-'}') — cannot confirm they are "
            "the same name; routed for human check")
