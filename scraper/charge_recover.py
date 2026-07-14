"""Recover real offense text when stored charge is a state/case-number stub."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from scraper.charge_sanitize import first_offense_from_fields, is_non_charge


def recover_charge_from_record(record: Dict[str, Any]) -> Optional[str]:
    """Return offense text from raw_json fields, or None."""
    raw = record.get("raw_json")
    if not raw:
        return None
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    fields = data.get("fields") or data.get("detail_fields") or {}
    if not isinstance(fields, dict):
        return None
    offense = first_offense_from_fields(fields.items())
    if offense and not is_non_charge(offense):
        return offense
    return None
