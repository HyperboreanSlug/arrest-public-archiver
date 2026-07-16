"""Strip mugshots.com court/registry field chrome from charge blobs.

CO / CA sex-offender and conviction dumps often glue statute codes, dates,
and repeated Description text into the charge string, e.g.::

    ATTEMPT SEX ASSAULT …; Statute 18-3-402(1)(A) Description ATTEMPT …
    Conviction Date 02-23-2017

    SEXUAL BATTERY; Offense Code 243.4(a) 290 Description SEXUAL BATTERY
    … Year of Last Conviction Year of Last Release
"""
from __future__ import annotations

import re
from typing import List

_SPLIT = re.compile(r"\s*[;|]\s*")

# CO: lead; Statute … Description … Conviction Date …
_CO_STATUTE = re.compile(
    r"(?is)^(?P<lead>.+?)\s*;?\s*Statute\b(?:(?!\bDescription\b).)*"
    r"\bDescription\s+(?P<body>.+?)\s+Conviction\s+Date\b"
)
# Bare Description … Conviction Date (no usable lead)
_CO_DESC_ONLY = re.compile(
    r"(?is)\bDescription\s+(?P<body>.+?)\s+Conviction\s+Date\b"
)
# CA: lead; Offense Code … Description … [Year of Last / Date Convicted]
_OFFENSE_CODE = re.compile(
    r"(?is)^(?P<lead>.+?)\s*;?\s*Offense\s+Code\b(?:(?!\bDescription\b).)*"
    r"\bDescription\s+(?P<body>.+?)"
    r"(?=\s+Year\s+of\s+Last|\s+Date\s+Convicted|\s+Date\s+Released|\s*$)"
)
# CA: Statute Number(s) … Crime … Jurisdiction/Conviction Date
_STATUTE_NUMS = re.compile(
    r"(?is)Statute\s+Number\(s\)\s+\S+\s+Crime\s+(?P<body>.+?)"
    r"(?=\s+Jurisdiction|\s+Conviction\s+Date|\s+Place\s+of\s+Crime|\s*$)"
)
# lead; Description … Date Convicted / Release …
_DESC_DATE_CONV = re.compile(
    r"(?is)^(?P<lead>.+?)\s*;?\s*Description\s+(?P<body>.+?)"
    r"(?=\s+Date\s+Convicted|\s+Year\s+of\s+Last|\s+Conviction\s+State|"
    r"\s+Release\s+Date|\s+Date\s+Released|\s+Details\b|\s*$)"
)
# AR court history: lead; Offense … Sentence Date / Case # / Sentence Length
_AR_OFFENSE = re.compile(
    r"(?is)^(?P<lead>.+?)\s*;\s*Offense\s+(?P<body>.+?)"
    r"(?=\s+Sentence\s+Date|\s+County\b|\s+Case\s*#|\s+Sentence\s+Length|\s*$)"
)
# #1 #2 … Offense BODY Sentence Date …
_HASH_OFFENSE = re.compile(
    r"(?is)(?:#\d+\s*)+\s*Offense\s+(?P<body>.+?)"
    r"(?=\s+Sentence\s+Date|\s+County\b|\s+Case\s*#|\s+Sentence\s+Length|\s*$)"
)
# Trailing registry meta (when still glued after primary extract)
_TRAIL_META = re.compile(
    r"(?is)\s+(?:"
    r"Conviction\s+Date|Date\s+Convicted|Year\s+of\s+Last|"
    r"Conviction\s+State|Release\s+Date|Date\s+Released|"
    r"Sentence\s+Date|Sentence\s+Length|Place\s+of\s+Crime|"
    r"Victim\s+of\s+Crime|Jurisdiction\b|Details\b"
    r")\b.*$"
)
_HAS_REGISTRY = re.compile(
    r"(?i)(?:\bStatute\b.+\bDescription\b|"
    r"\bOffense\s+Code\b|"
    r"\bStatute\s+Number\(s\)|"
    r"\bConviction\s+Date\b|"
    r"\bDate\s+Convicted\b|"
    r"\bYear\s+of\s+Last\s+Conviction\b|"
    r"\bSentence\s+Date\b|"
    r"(?:#\d+\s*){2,}\s*Offense\b)"
)
# Leading code fragment on description extras: 288(a) - LEWD …
_LEAD_CODE = re.compile(
    r"(?ix)^\s*"
    r"(?:"
    r"\d{1,4}(?:\.\d+)?(?:\([a-z0-9]+\))*\s*[-–—:]\s+"
    r"|\d{1,4}(?:\.\d+)?(?:\([a-z0-9]+\))*\s+"
    r")"
)


def _norm(text: str) -> str:
    return " ".join((text or "").replace("\u00a0", " ").split()).strip(" \t,.;:-")


def has_registry_chrome(text: str) -> bool:
    return bool(_HAS_REGISTRY.search(text or ""))


def _dedupe(parts: List[str]) -> List[str]:
    out: List[str] = []
    seen: set = set()
    for p in parts:
        s = _norm(p)
        if not s or len(s) < 2:
            continue
        key = s.casefold()
        if key in seen:
            continue
        # Drop exact-prefix duplicates of a longer kept label
        if any(key == k or key.startswith(k + " ") or k.startswith(key + " ") for k in seen):
            # Prefer the longer form already kept; skip shorter restate
            if any(k.startswith(key) and k != key for k in seen):
                continue
            # Replace shorter kept with longer
            for i, prev in enumerate(out):
                if prev.casefold() in key and key.startswith(prev.casefold()):
                    out[i] = s
                    seen.discard(prev.casefold())
                    seen.add(key)
                    break
            else:
                seen.add(key)
                out.append(s)
            continue
        seen.add(key)
        out.append(s)
    return out


def _extras_from_body(lead: str, body: str) -> List[str]:
    """Return offense pieces in *body* that are not just a restatement of *lead*."""
    body_n = _TRAIL_META.sub("", _norm(body))
    body_n = _norm(body_n)
    if not body_n:
        return []
    lead_n = _norm(lead)
    if not lead_n:
        return [body_n]
    low_body = body_n.casefold()
    low_lead = lead_n.casefold()
    if low_body == low_lead:
        return []
    if low_body.startswith(low_lead):
        rem = _norm(body_n[len(lead_n) :])
        rem = _LEAD_CODE.sub("", rem)
        rem = _norm(rem)
        return [rem] if rem and rem.casefold() != low_lead else []
    # Body may start with a code + restatement of lead, then extra offenses
    stripped = _LEAD_CODE.sub("", body_n)
    stripped = _norm(stripped)
    if stripped.casefold() == low_lead:
        return []
    if stripped.casefold().startswith(low_lead):
        rem = _norm(stripped[len(lead_n) :])
        rem = _LEAD_CODE.sub("", rem)
        rem = _norm(rem)
        return [rem] if rem else []
    # Entire body is a different offense string
    if low_lead in low_body:
        # Remove first occurrence of lead words; keep remainder if meaningful
        idx = low_body.find(low_lead)
        rem = _norm(body_n[:idx] + " " + body_n[idx + len(lead_n) :])
        rem = _LEAD_CODE.sub("", rem)
        rem = _norm(rem)
        if rem and rem.casefold() != low_lead:
            return [rem]
        return []
    return [body_n]


def strip_registry_chrome(text: str) -> str:
    """Return offense-only text; unchanged when no court/registry chrome."""
    s = _norm(text)
    if not s or not has_registry_chrome(s):
        return s

    # #1 #2 … Offense … Sentence Date (AR multi-row dump)
    m = _HASH_OFFENSE.search(s)
    if m:
        body = _norm(m.group("body"))
        body = _TRAIL_META.sub("", body)
        return _norm(body) or s

    m = _STATUTE_NUMS.search(s)
    if m:
        return _norm(m.group("body")) or s

    for pat in (_CO_STATUTE, _OFFENSE_CODE, _DESC_DATE_CONV, _AR_OFFENSE):
        m = pat.search(s)
        if not m:
            continue
        lead = _norm(m.group("lead"))
        body = m.group("body")
        # Lead may still start with "Statute …" when only body is useful
        if re.match(r"(?i)^statute\b", lead):
            lead = ""
        parts = ([lead] if lead else []) + _extras_from_body(lead, body)
        parts = _dedupe(parts)
        if parts:
            return "; ".join(parts)

    m = _CO_DESC_ONLY.search(s)
    if m:
        body = _TRAIL_META.sub("", _norm(m.group("body")))
        if body:
            return body

    # Last resort: cut trailing conviction/sentence meta from each segment
    segs = [p for p in _SPLIT.split(s) if p and p.strip()] or [s]
    kept: List[str] = []
    for seg in segs:
        cut = _TRAIL_META.sub("", _norm(seg))
        # Drop pure statute/code segments
        if re.match(r"(?i)^(?:statute|offense\s+code)\b", cut):
            continue
        if cut:
            kept.append(cut)
    out = _dedupe(kept)
    return "; ".join(out) if out else s
