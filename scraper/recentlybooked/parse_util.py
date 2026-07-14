"""Shared helpers for RecentlyBooked HTML parsers."""
from __future__ import annotations

import re
from typing import Dict, List, Optional
from urllib.parse import urlparse

from bs4 import Tag

BASE_URL = "https://recentlybooked.com"
# Booking id after "_" may be empty (e.g. /ca/sacramento/name~1210_).
_DETAIL_PATH = re.compile(
    r"^/([a-z]{2})/([a-z0-9-]+)/([^/]+~([a-z0-9-]+)_([a-z0-9-]*))/?$",
    re.IGNORECASE,
)
_LABEL_ALIASES = {
    "race": "race",
    "sex": "sex",
    "gender": "sex",
    "age": "age",
    "booking date": "booking_date",
    "booked date": "booking_date",
    "booking date/time": "booking_date",
    "arrest date": "arrest_date",
    "charge": "charge_description",
    "charges": "charge_description",
    "charge description": "charge_description",
    "agency": "agency",
    "arresting agency": "agency",
    "facility": "facility",
    "booking id": "booking_id",
    "height": "height",
    "weight": "weight",
    "hair": "hair",
    "eyes": "eyes",
}
_NAME_SUFFIXES = {
    "jr",
    "jr.",
    "sr",
    "sr.",
    "ii",
    "iii",
    "iv",
    "v",
    "2nd",
    "3rd",
    "4th",
}


def _text(tag: Optional[Tag]) -> Optional[str]:
    if tag is None:
        return None
    value = tag.get_text(" ", strip=True)
    return value or None


def _detail_match(url: str) -> Optional[re.Match[str]]:
    return _DETAIL_PATH.match(urlparse(url).path)


def _name_parts(name: Optional[str]) -> Dict[str, str]:
    if not name:
        return {}
    cleaned = " ".join(name.replace(",", " ").split())
    parts = cleaned.split()
    if not parts:
        return {}
    result: Dict[str, str] = {"full_name": cleaned, "name": cleaned}
    suffix_parts: List[str] = []
    while len(parts) > 1 and parts[-1].lower() in _NAME_SUFFIXES:
        suffix_parts.insert(0, parts.pop())
    if suffix_parts:
        result["name_suffix"] = " ".join(suffix_parts)
    if len(parts) == 1:
        result["last_name"] = parts[0]
    else:
        result["first_name"] = parts[0]
        result["last_name"] = parts[-1]
        if len(parts) > 2:
            result["middle_name"] = " ".join(parts[1:-1])
    return result
