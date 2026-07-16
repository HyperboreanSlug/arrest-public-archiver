"""Polish and proper-case charge text for export mugshot cards."""
from __future__ import annotations

import re

# Kept as full uppercase on cards (never mixed case).
_CARD_ACRONYMS = {
    "dui": "DUI",
    "dwi": "DWI",
    "owi": "OWI",
    "ovi": "OVI",
    "fta": "FTA",
    "ice": "ICE",
    "id": "ID",
    "dl": "DL",
    "mv": "MV",
    "be": "B&E",
    "b&e": "B&E",
    "usc": "USC",
    "leo": "LEO",
}

# Leading statute / booking codes before the offense words.
_LEADING_CODE = re.compile(
    r"(?ix)^\s*"
    r"(?:"
    r"(?:\d+\s*[.\-]\s*)+\d+\s*[-–—:]\s+"  # 97.5.23 -  / 5 - 14 - 108 -
    r"|\d{2,5}\s*[-–—:]\s+"  # 0950 -
    r"|\d+\s+Usc\b[\w\s().]*?[-–—]\s+"  # 18 USC 2252A(a)(2) -
    r")"
)
_ATTEMPT = re.compile(
    r"(?i)\bAttempt(?:ed)?\s+To\s+Commit\b|\bAttempt(?:ed)?\s+To\b|\bAttempt\b(?=\s+\w)"
)
_ORDINAL_DEGREE = re.compile(
    r"\b(\d+)\s*[-–—]?\s*(?:St|Nd|Rd|Th)\b(?:\s+Degree)?",
    re.IGNORECASE,
)
_ORDINAL_GLUED = re.compile(
    r"\b(\d+)(st|nd|rd|th)\b(?:\s+Degree)?",
    re.IGNORECASE,
)
_PAGE_JUNK = re.compile(r"(?i)\s*[-–—]?\s*Page\s*:\s*\d+.*$")
_PAREN_META = re.compile(
    r"\([^)]*(?:Lev|Deg|Count|Principal|Page)[^)]*\)",
    re.IGNORECASE,
)
_TRAILING_ROLE = re.compile(
    r"(?i)\s*[-–—]\s*(?:Principal|Accomplice|Aider|Abettor)\b.*$"
)
_BAC_FRAG = re.compile(r"(?i)\s*[.\-]\s*0?\.\d{1,3}\b|\s+\.\s+\d{2}\b")
_SEX_CHILD = re.compile(
    r"(?i)\b((?:Aggravated\s+)?(?:Sexual\s+)?(?:Assault|Abuse|Battery|Rape))"
    r"\s+Child\b"
)
# CO statutory element language left on booking labels (not a separate crime).
_OVERCOME_WILL = re.compile(r"(?i)\s+overcome\s+victim'?s?\s+will\b")
# Leftover court-history meta (sanitize usually removes; belt-and-suspenders).
_CARD_TRAIL_META = re.compile(
    r"(?is)\s+(?:"
    r"Conviction\s+Date|"
    r"Date\s+Convicted|"
    r"Year\s+of\s+Last(?:\s+Conviction|\s+Release)?|"
    r"Conviction\s+State|"
    r"Release\s+Date|"
    r"Date\s+Released|"
    r"Sentence\s+Date|"
    r"Sentence\s+Length|"
    r"Offense\s+Code\b|"
    r"Jurisdiction\b|"
    r"Place\s+of\s+Crime|"
    r"Victim\s+of\s+Crime"
    r").*$"
)
_CLASS_TAIL = re.compile(
    r"(?i)\s+(?:[FM]\s*\d{1,2}|\([FM]\d{0,2}\))\s*$"
)
_DOT_ORDINAL = re.compile(r"\.(?=\d+(?:st|nd|rd|th)\b)", re.I)
_DEGREE_DEG = re.compile(
    r"(?i)\b(\d+(?:st|nd|rd|th)\s+Degree)\s+Deg(?:ree)?\b"
)
_BARE_DEG = re.compile(r"(?i)\b(\d+(?:st|nd|rd|th))\s+Deg\b")
_WITH_SLASH = re.compile(r"(?i)\bw\s*/\s*")
_SMALL_WORDS = frozenset(
    {"a", "an", "and", "of", "or", "the", "to", "for", "in", "on", "by", "with"}
)
_AFFIX = re.compile(r"^([(\"'\[]*)(.*?)([.,;:\"'\)\]]*)$")


def limit_charge_labels(text: str, max_labels: int) -> str:
    """Keep the first N semicolon-separated labels so cards stay readable."""
    if max_labels <= 0:
        return text
    parts = [p.strip() for p in str(text or "").split(";") if p.strip()]
    if len(parts) <= max_labels:
        return "; ".join(parts)
    return "; ".join(parts[:max_labels]) + "; …"


def _ordinal_degree(match: re.Match) -> str:
    n = int(match.group(1))
    mod100 = n % 100
    if 10 < mod100 < 14:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf} Degree"


def polish_card_charge(text: str) -> str:
    """Strip codes/meta and normalize phrasing for share-card readability."""
    parts: list[str] = []
    seen: set[str] = set()
    for raw in str(text or "").split(";"):
        s = " ".join(raw.split()).strip(" -–—:")
        if not s:
            continue
        s = _PAGE_JUNK.sub("", s)
        s = _CARD_TRAIL_META.sub("", s)
        s = _PAREN_META.sub(" ", s)
        s = _TRAILING_ROLE.sub("", s)
        s = _LEADING_CODE.sub("", s)
        s = _OVERCOME_WILL.sub("", s)
        s = _WITH_SLASH.sub("With ", s)
        s = _DOT_ORDINAL.sub(" ", s)
        s = _CLASS_TAIL.sub("", s)
        s = _ATTEMPT.sub("Attempted", s)
        s = _ORDINAL_GLUED.sub(_ordinal_degree, s)
        s = _ORDINAL_DEGREE.sub(_ordinal_degree, s)
        s = _DEGREE_DEG.sub(r"\1", s)
        s = _BARE_DEG.sub(r"\1 Degree", s)
        s = _SEX_CHILD.sub(r"\1 of a Child", s)
        s = _BAC_FRAG.sub("", s)
        s = re.sub(r"\s+", " ", s).strip(" -–—:;")
        if not s:
            continue
        key = s.casefold()
        if key in seen:
            continue
        seen.add(key)
        parts.append(s)
    return "; ".join(parts)


def _proper_word(core: str, *, first: bool) -> str:
    """Force proper case for one word; known acronyms stay uppercase."""
    if not core:
        return core
    low = core.lower()
    if low in _CARD_ACRONYMS:
        return _CARD_ACRONYMS[low]
    om = re.fullmatch(r"(\d+)(st|nd|rd|th)", low)
    if om:
        return om.group(1) + om.group(2)
    if re.fullmatch(r"[\d$.,<>%=+\-]+", core):
        return core
    if not first and low in _SMALL_WORDS:
        return low
    if "-" in core and not core.startswith("-"):
        bits = core.split("-")
        return "-".join(
            _proper_word(b, first=(first and i == 0)) for i, b in enumerate(bits)
        )
    if re.search(r"[A-Za-z]", core):
        return low[:1].upper() + low[1:] if low else core
    return core


def card_charge_text(text: str) -> str:
    """Proper-case every charge line (no mixed ALLCAPS/Title leftovers)."""
    parts: list[str] = []
    for raw in str(text or "").split(";"):
        s = " ".join(raw.split()).strip()
        if not s:
            continue
        s = re.sub(r"\(\s+", "(", s)
        s = re.sub(r"\s+\)", ")", s)
        words = s.split()
        fixed: list[str] = []
        for i, w in enumerate(words):
            m = _AFFIX.match(w)
            pre, core, suf = m.groups() if m else ("", w, "")
            fixed.append(pre + _proper_word(core, first=(i == 0)) + suf)
        parts.append(" ".join(fixed))
    return "; ".join(parts) if parts else str(text or "").strip()
