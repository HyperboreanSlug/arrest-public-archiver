"""Summarize raw charge text into short stable labels for misclassify tables.

Example: "ICE", "US IMMIGRATION", "IMMIGRATION HOLD" → "ICE IMMIGRATION HOLD"
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

from scraper.charge_summary_rules import _COMPILED

# Split multi-charge blobs from jails that concatenate bookings.
_SPLIT = re.compile(r"\s*[;|]\s*|\s{2,}|\s*/\s*(?=[A-Z])")
_NOISE = re.compile(
    r"(?i)"
    r"(\$\d[\d,.]*)|"
    r"(active\s+bond\b.*$)|"
    r"(bond-\d+\w*)|"
    r"(n/a)+"
)


def _clean_segment(text: str) -> str:
    s = " ".join((text or "").replace("\u00a0", " ").split())
    s = _NOISE.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip(" \t,.;:-")
    return s


def _split_charges(blob: str) -> List[str]:
    raw = _clean_segment(blob)
    if not raw:
        return []
    parts = [p for p in _SPLIT.split(raw) if p and p.strip()]
    # De-dupe consecutive identical segments (jails often repeat FTA thrice).
    out: List[str] = []
    seen_l: set = set()
    for p in parts:
        c = _clean_segment(p)
        key = c.lower()
        if not c or key in seen_l:
            continue
        # Skip pure agency garbage fragments
        if len(c) < 2:
            continue
        seen_l.add(key)
        out.append(c)
    return out or ([raw] if raw else [])


def _match_one(segment: str) -> str:
    text = segment.strip()
    if not text:
        return ""
    for label, patterns in _COMPILED:
        for pat in patterns:
            if pat.search(text):
                return label
    # Fallback: compact original (upper, trim length)
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) > 48:
        compact = compact[:45].rstrip() + "…"
    return compact.upper() if compact == compact.lower() else compact


def summarize_charge(record_or_text: Any) -> str:
    """
    Return a short display summary for charge text or an arrest record.

    Multi-charge strings are split, each segment summarized, then unique
    labels joined with ``; `` (priority order preserved).
    """
    if record_or_text is None:
        return "—"
    if isinstance(record_or_text, dict):
        parts = [
            record_or_text.get("charge_description"),
            record_or_text.get("charge_group"),
            record_or_text.get("offense"),
            record_or_text.get("offense_description"),
            record_or_text.get("statute"),
        ]
        blob = " | ".join(str(p) for p in parts if p and str(p).strip())
    else:
        blob = str(record_or_text)
    segments = _split_charges(blob)
    if not segments:
        return "—"
    labels: List[str] = []
    seen: set = set()
    for seg in segments:
        lab = _match_one(seg)
        if not lab:
            continue
        key = lab.upper()
        if key in seen:
            continue
        seen.add(key)
        labels.append(lab)
    return "; ".join(labels) if labels else "—"


def summarize_charge_list(records: Sequence[Dict[str, Any]]) -> List[str]:
    return [summarize_charge(r) for r in records]
