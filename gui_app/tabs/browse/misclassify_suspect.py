"""Filter browse rows to surname-vs-stated-race misclassification suspects."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from gui_app.tabs.browse.misclassify_constants import (
    BROWSE_ACTUAL_RACES,
    actual_race_filter_values,
)
from scraper.searcher import ethnicity_review_verdict


def resolve_actual_filter(actual: Optional[str]) -> Tuple[Optional[str], Optional[List[str]]]:
    """Map UI actual-race filter → search kwargs (single value or IN-list)."""
    if actual == "(Unset)":
        return "unset", None
    if actual in BROWSE_ACTUAL_RACES:
        return None, actual_race_filter_values(actual)
    if actual not in ("All", "", None):
        return actual, None
    return None, None


def matches_confirmation(record: Dict[str, Any], review: Optional[str]) -> bool:
    """True when *record* matches the Verification/confirmation filter key."""
    if review is None or review in ("", "all", "*"):
        return True
    verdict = ethnicity_review_verdict(record)
    key = str(review).strip().lower()
    if key in ("unreviewed", "unverified", "none", "unset"):
        return not verdict
    return verdict == key


def filter_suspected_misclass(
    records: List[Dict[str, Any]],
    *,
    min_confidence: float = 0.5,
    ethnic_db: Any = None,
    ethnicity_review: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Keep only rows where the ethnic surname model disagrees with stated race.

    Same core rules as ``ArrestSearcher.analyze_ethnicities`` (min confidence,
    not compatible with recorded race). When *ethnicity_review* is set (e.g.
    ``unreviewed``), confirmed rows are excluded so they never reappear after
    confirmation.
    """
    from scraper.searcher_names import (
        _first_name_from_record,
        _last_name_from_record,
        _middle_name_from_record,
    )
    from scraper.searcher_race import _is_compatible

    if ethnic_db is None:
        from scraper.ethnic_names import EthnicNameDatabase

        ethnic_db = EthnicNameDatabase()

    out: List[Dict[str, Any]] = []
    for rec in records:
        if not matches_confirmation(rec, ethnicity_review):
            continue
        last = _last_name_from_record(rec)
        if not last:
            continue
        first = _first_name_from_record(rec)
        middle = _middle_name_from_record(rec)
        recorded_race = (rec.get("race") or "").strip()
        recorded_eth = (rec.get("ethnicity") or "").strip() or None
        likely, conf, _ = ethnic_db.classify_by_name(
            last,
            first_name=first or None,
            middle_name=middle or None,
        )
        if conf < min_confidence or likely == "Unknown":
            continue
        if _is_compatible(likely, recorded_race, recorded_eth):
            continue
        # Annotate for Actual race column / sidebar when unset or model-driven.
        rec = dict(rec)
        rec["likely_ethnicity"] = likely
        rec["name_confidence"] = conf
        out.append(rec)
    out.sort(key=lambda r: float(r.get("name_confidence") or 0), reverse=True)
    return out
