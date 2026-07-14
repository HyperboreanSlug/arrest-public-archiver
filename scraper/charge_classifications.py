"""
Classify arrest charge text into coarse offense categories for filtering.

Used on import (stored as charge_category) and at query time as fallback.
Primary product still ethnic misclassification; charge filters narrow that analysis.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from scraper.charge_rules import _COMPILED
from scraper.charge_summary import summarize_charge

# Stable keys used in CLI/GUI filters (order is display order)
CHARGE_CATEGORIES: List[Tuple[str, str]] = [
    ("sex_crimes", "Sex crimes"),
    ("violent", "Violent / assault"),
    ("weapons", "Weapons"),
    ("burglary_be", "Burglary / B&E"),
    ("theft_property", "Theft / property"),
    ("robbery", "Robbery"),
    ("drugs", "Drugs / controlled substances"),
    ("dui_traffic", "DUI / traffic"),
    ("fraud_financial", "Fraud / financial"),
    ("domestic", "Domestic / family"),
    ("public_order", "Public order"),
    ("homicide", "Homicide"),
    ("other", "Other"),
    ("unknown", "Unknown / blank"),
]

CATEGORY_KEYS = [k for k, _ in CHARGE_CATEGORIES]
CATEGORY_LABELS = {k: lab for k, lab in CHARGE_CATEGORIES}


def category_label(key: str) -> str:
    return CATEGORY_LABELS.get((key or "").strip().lower(), key or "Unknown")


def list_category_choices(include_all: bool = True) -> List[str]:
    keys = list(CATEGORY_KEYS)
    if include_all:
        return ["all"] + keys
    return keys


def _charge_blob(record_or_text: Any) -> str:
    if record_or_text is None:
        return ""
    if isinstance(record_or_text, str):
        return record_or_text
    if not isinstance(record_or_text, dict):
        return str(record_or_text)
    parts = [
        record_or_text.get("charge_description"),
        record_or_text.get("charge_group"),
        record_or_text.get("charge_level"),
        record_or_text.get("charge_class"),
        record_or_text.get("statute"),
        record_or_text.get("offense"),
        record_or_text.get("offense_description"),
    ]
    return " | ".join(str(p) for p in parts if p and str(p).strip())


def classify_charge(record_or_text: Any) -> str:
    """
    Return a category key for charge text or an arrest record dict.

    Empty / unmatchable → "unknown" or "other".
    """
    text = _charge_blob(record_or_text)
    if not text or not text.strip():
        return "unknown"
    for cat, patterns in _COMPILED:
        for pat in patterns:
            if pat.search(text):
                return cat
    return "other"


def classify_record(record: Dict[str, Any]) -> str:
    """Set and return charge_category on *record* (mutates)."""
    cat = classify_charge(record)
    # Prefer pre-set valid category if already classified
    existing = (record.get("charge_category") or "").strip().lower()
    if existing in CATEGORY_LABELS and existing not in ("", "unknown"):
        # re-classify blank/unknown; keep known only if reclass is other? Always reclassify for consistency
        pass
    record["charge_category"] = cat
    # Short display title for misclassify / browse tables
    try:
        record["charge_summary"] = summarize_charge(record)
    except Exception:
        record["charge_summary"] = ""
    return cat


def charge_matches_filter(record: Dict[str, Any], charge_filter: Optional[str]) -> bool:
    """True if record matches charge category filter (None/'all' = always)."""
    if not charge_filter or str(charge_filter).strip().lower() in ("all", "*", ""):
        return True
    want = str(charge_filter).strip().lower()
    have = (record.get("charge_category") or "").strip().lower()
    if not have or have == "unknown":
        have = classify_charge(record)
    return have == want


def summarize_categories(records: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    counts: Dict[str, int] = {}
    for r in records:
        cat = (r.get("charge_category") or classify_charge(r)).lower()
        counts[cat] = counts.get(cat, 0) + 1
    out = []
    for key, label in CHARGE_CATEGORIES:
        if key in counts:
            out.append({"category": key, "label": label, "count": counts[key]})
    for key, n in sorted(counts.items(), key=lambda x: -x[1]):
        if key not in CATEGORY_LABELS:
            out.append({"category": key, "label": key, "count": n})
    return out
