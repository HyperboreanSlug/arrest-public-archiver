"""Summarize raw charge text into short stable labels for tables/cards.

Expands jail abbreviations, maps segments to one label each, joins unique labels.
Unmatched segments become OTHER (no raw docket strings).
"""
from __future__ import annotations

import re
from typing import Any, List, Sequence

from scraper.charge_expand import expand_charge_text
from scraper.charge_summary_rules import _COMPILED

_SPLIT = re.compile(r"\s*[;|]\s*|\s{2,}|(?<![A-Za-z])\s*/\s*(?=[A-Z])")
_NOISE = re.compile(
    r"(?i)(\$\d[\d,.]*)|(active\s+bond\b.*$)|(bond-\d+\w*)|(n/a)+"
)
_STRIP_PREFIX = re.compile(r"(?i)^\s*MTR\s*[-–—:]\s*")
_STRIP_OOC = re.compile(r"(?i)^\s*out\s+of\s+county(?:\s+hold)?\s*[/:\-]\s*")
# For matching only: strip citation noise without expanding tokens.
_MATCH_NOISE = re.compile(
    r"(?i)"
    r"(\(\s*[a-z]{1,3}\s*\))|"  # (MA) (MB)
    r"(\b\d{1,5}\s*[-–—]\s*)|"  # leading count codes
    r"(\[\s*[^\]]*\])|"
    r"(\bcount\s+of\b)|"
    r"(\b\d+\s*counts?\s+of\b)"
)


def _clean_segment(text: str) -> str:
    s = " ".join((text or "").replace("\u00a0", " ").split())
    s = _NOISE.sub(" ", s)
    s = _STRIP_PREFIX.sub("", s)
    m = _STRIP_OOC.match(s)
    if m:
        body = s[m.end() :].strip()
        from scraper.charge_admin import is_place_case_blob
        from scraper.charge_sanitize import is_non_charge

        if body and not is_place_case_blob(body) and not is_non_charge(body):
            body = re.split(
                r"\s*/\s*(?=[A-Z][A-Z\s]+(?:CO|COUNTY)\b)", body, maxsplit=1
            )[0]
            s = body
    return re.sub(r"\s+", " ", s).strip(" \t,.;:-")


def _split_charges(blob: str) -> List[str]:
    raw = _clean_segment(blob)
    if not raw:
        return []
    parts = [p for p in _SPLIT.split(raw) if p and p.strip()]
    out: List[str] = []
    seen_l: set = set()
    for p in parts:
        c = _clean_segment(p)
        key = c.lower()
        if not c or key in seen_l or len(c) < 2:
            continue
        seen_l.add(key)
        out.append(c)
    return out or ([raw] if raw else [])


def _match_blob(text: str) -> str:
    if not text:
        return ""
    for label, patterns in _COMPILED:
        for pat in patterns:
            if pat.search(text):
                return label
    return ""


def _match_one(segment: str) -> str:
    """Map one charge segment to a canonical label (or OTHER)."""
    from scraper.charge_sanitize import is_non_charge

    raw = (segment or "").strip()
    if not raw or is_non_charge(raw):
        return ""
    expanded = expand_charge_text(raw).strip() or raw
    compact = re.sub(r"\s+", " ", raw)
    match_ready = _MATCH_NOISE.sub(" ", compact)
    match_ready = re.sub(r"\s+", " ", match_ready).strip()
    for candidate in (expanded, raw, match_ready, match_ready.lower()):
        hit = _match_blob(candidate)
        if hit:
            return hit
    return "OTHER"


def summarize_charge(record_or_text: Any) -> str:
    """Short standardized label(s) for charge text or an arrest record."""
    from scraper.charge_expand import expand_charge
    from scraper.charge_sanitize import is_non_charge, sanitize_charge_text

    if record_or_text is None:
        return "—"
    if isinstance(record_or_text, dict):
        blob = expand_charge(record_or_text)
        if blob in ("", "—"):
            return "—"
    else:
        blob = sanitize_charge_text(str(record_or_text))
        if not blob or is_non_charge(blob):
            return "—"
    segments = _split_charges(blob)
    if not segments:
        return "—"
    labels: List[str] = []
    seen: set = set()
    for seg in segments:
        if is_non_charge(seg):
            continue
        lab = _match_one(seg)
        if not lab or is_non_charge(lab):
            continue
        key = lab.upper()
        if key in seen:
            continue
        seen.add(key)
        labels.append(lab)
    return "; ".join(labels) if labels else "—"


def summarize_charge_list(records: Sequence[Dict[str, Any]]) -> List[str]:
    return [summarize_charge(r) for r in records]
