"""Browse Misclassify column labels, verification, and actual-race buckets."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from scraper.searcher import ethnicity_review_verdict

BROWSE_COLS = [
    "name",
    "race",
    "actual",
    "review",
    "charge",
    "state",
    "date",
    "source",
]
BROWSE_LABELS = {
    "name": "Name",
    "race": "Stated race",
    "actual": "Actual race",
    "review": "Confirmation",
    "charge": "Charge",
    "state": "State",
    "date": "Date",
    "source": "Source",
}
# Confirmation status filter (default Unverified — confirmed never reappear).
VERIFICATION_FILTERS = [
    "Unverified",
    "Confirmed correct",
    "Confirmed incorrect",
    "All",
]
VERIFICATION_QUERY = {
    "unverified": "unreviewed",
    "unreviewed": "unreviewed",
    "confirmed correct": "correct",
    "correct": "correct",
    "confirmed incorrect": "incorrect",
    "incorrect": "incorrect",
    "all": None,
}

# Browse actual-race picker / filter: four coarse buckets (Indian + MENA merged).
_INDIAN_MENA = "Indian / MENA"
BROWSE_ACTUAL_RACES = ["White", "Black", "Hispanic", _INDIAN_MENA]

# Stored / analyzer labels → bucket (lowercase keys).
_ACTUAL_RACE_TO_BUCKET = {
    "white": "White",
    "european": "White",
    "portuguese": "White",
    "jewish": "White",
    "black": "Black",
    "african american": "Black",
    "african-american": "Black",
    "hispanic": "Hispanic",
    "latino": "Hispanic",
    "latina": "Hispanic",
    "latinx": "Hispanic",
    # South Asian Indian + MENA share one actual-race bucket (same as stated race).
    "indian / mena": _INDIAN_MENA,
    "indian/mena": _INDIAN_MENA,
    "indian / nema": _INDIAN_MENA,
    "indian/nema": _INDIAN_MENA,
    "indian": _INDIAN_MENA,
    "south asian": _INDIAN_MENA,
    "south-asian": _INDIAN_MENA,
    "mena": _INDIAN_MENA,
    "arabic": _INDIAN_MENA,
    "arab": _INDIAN_MENA,
    "middle eastern": _INDIAN_MENA,
    "middle-eastern": _INDIAN_MENA,
    "north african": _INDIAN_MENA,
    "north-african": _INDIAN_MENA,
    "persian": _INDIAN_MENA,
    "pakistani": _INDIAN_MENA,
    "bangladeshi": _INDIAN_MENA,
    "sri lankan": _INDIAN_MENA,
}


def verification_query(label: Optional[str]) -> Optional[str]:
    key = (label or "Unverified").strip().lower()
    if key in VERIFICATION_QUERY:
        return VERIFICATION_QUERY[key]
    return "unreviewed"


def verification_label(record: Dict[str, Any]) -> str:
    verdict = ethnicity_review_verdict(record)
    if verdict == "correct":
        return "Confirmed correct"
    if verdict == "incorrect":
        return "Confirmed incorrect"
    return "Unverified"


def bucket_actual_race(label: Optional[str]) -> Optional[str]:
    """Map a free-form actual/likely label to White/Black/Hispanic/Indian / MENA."""
    raw = " ".join(str(label or "").replace("_", " ").split()).strip()
    if not raw:
        return None
    low = raw.lower()
    # Do not treat Native American / American Indian as South Asian Indian.
    if "native american" in low or low.startswith("american indian"):
        return None
    hit = _ACTUAL_RACE_TO_BUCKET.get(low)
    if hit:
        return hit
    # Prefix match only: "European (english)" → White, "Indian (high_confidence)" → …
    # (Avoid bare word search so "American Indian" is not mapped to Indian / MENA.)
    for key, bucket in sorted(
        _ACTUAL_RACE_TO_BUCKET.items(), key=lambda kv: len(kv[0]), reverse=True
    ):
        if (
            low.startswith(key + " ")
            or low.startswith(key + "(")
            or low.startswith(key + "/")
        ):
            return bucket
    return None


def actual_race_filter_values(bucket: str) -> List[str]:
    """DB / model values that count as *bucket* (exact + prefixes via search)."""
    b = (bucket or "").strip()
    if not b:
        return []
    out = {b}
    low = b.lower()
    if low == "white":
        out.update({"White", "European", "Portuguese", "Jewish"})
    elif low == "black":
        out.update({"Black", "African American", "African-American"})
    elif low == "hispanic":
        out.update({"Hispanic", "Latino", "Latina"})
    elif low in ("indian / mena", "indian/mena", "mena"):
        out.update(
            {
                _INDIAN_MENA,
                "Indian / MENA",
                "MENA",
                "Indian",
                "Arabic",
                "Arab",
                "Middle Eastern",
                "Middle-Eastern",
                "North African",
                "North-African",
                "South Asian",
                "Persian",
                "Pakistani",
                "Bangladeshi",
            }
        )
    return sorted(out)


def picker_actual_race(label: Optional[str], options: List[str]) -> str:
    """Value to show in a bucketed actual-race combo.

    Never inject charge/docket junk into the dropdown: if the label cannot be
    mapped to a known option, fall back to the first option (or Unknown).
    """
    raw = " ".join(str(label or "").split()).strip() or "Unknown"
    opts = list(options or [])
    if opts and set(opts) <= set(BROWSE_ACTUAL_RACES):
        bucket = bucket_actual_race(raw)
        if bucket and bucket in opts:
            return bucket
        if raw in opts:
            return raw
        return opts[0] if opts else "White"
    if raw in opts:
        return raw
    bucket = bucket_actual_race(raw)
    if bucket and bucket in opts:
        return bucket
    for fallback in ("Unknown", "Other", "White"):
        if fallback in opts:
            return fallback
    return opts[0] if opts else "White"


def actual_from_stated_race(recorded_race: Optional[str]) -> Optional[str]:
    """
    Map stated race → Browse actual-race value when marked classified correctly.

    Prefers White / Black / Hispanic / Indian / MENA; otherwise returns a clean
    display label (e.g. Asian) when the stated race is known.
    """
    from scraper.searcher import format_race_label

    raw = str(recorded_race or "").strip()
    if not raw:
        return None
    label = format_race_label(raw)
    if label == _INDIAN_MENA:
        return _INDIAN_MENA
    bucket = bucket_actual_race(label) or bucket_actual_race(raw)
    if bucket:
        return bucket
    if label and label not in ("Other/Unknown", "—", ""):
        return label
    return None
