"""Shared helpers for Busted Newspaper HTML parsers."""
from __future__ import annotations

import re
from typing import Dict, Optional
from urllib.parse import urlparse

from bs4 import Tag

BASE_URL = "https://bustednewspaper.com"
_DETAIL_PATH = re.compile(
    r"^/([a-z0-9-]+)/([^/]+)/(\d{8})/?$",
    re.IGNORECASE,
)
_COUNTY_PATH = re.compile(
    r"^/mugshots/([a-z0-9-]+)/([a-z0-9-]+)/?$",
    re.IGNORECASE,
)
_STATE_SLUG_TO_CODE = {
    "alabama": "AL",
    "arizona": "AZ",
    "arkansas": "AR",
    "florida": "FL",
    "georgia": "GA",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maryland": "MD",
    "michigan": "MI",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nevada": "NV",
    "new-jersey": "NJ",
    "new-mexico": "NM",
    "new-york": "NY",
    "north-carolina": "NC",
    "north-dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "south-carolina": "SC",
    "south-dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "virginia": "VA",
    "west-virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
}
_LABEL_ALIASES = {
    "name": "full_name",
    "dob": "date_of_birth",
    "age": "age",
    "race": "race",
    "sex": "sex",
    "gender": "sex",
    "booked": "booking_date",
    "booking date": "booking_date",
    "height": "height",
    "weight": "weight",
    "hair": "hair",
    "eye": "eyes",
    "eyes": "eyes",
}


def _text(tag: Optional[Tag]) -> Optional[str]:
    if tag is None:
        return None
    value = tag.get_text(" ", strip=True)
    return value or None


def _detail_match(url: str) -> Optional[re.Match[str]]:
    return _DETAIL_PATH.match(urlparse(url).path)


def state_code_from_slug(slug: str) -> str:
    """Map a Busted Newspaper state slug to a two-letter code when known."""
    key = (slug or "").strip().lower()
    return _STATE_SLUG_TO_CODE.get(key, key.upper()[:2] if key else "")


def normalize_county_slug(slug: str) -> str:
    """Normalize county slugs for storage (drop a trailing ``-county``)."""
    value = (slug or "").strip().lower()
    if value.endswith("-county"):
        return value[: -len("-county")]
    return value


def _name_parts(name: Optional[str]) -> Dict[str, str]:
    if not name:
        return {}
    cleaned = " ".join(name.replace(",", " ").split())
    if not cleaned:
        return {}
    if "," in (name or ""):
        last, _, rest = name.partition(",")
        last = last.strip()
        parts = rest.split()
        result: Dict[str, str] = {"full_name": cleaned, "name": cleaned}
        if last:
            result["last_name"] = last.title()
        if parts:
            result["first_name"] = parts[0].title()
            if len(parts) > 1:
                result["middle_name"] = " ".join(p.title() for p in parts[1:])
        return result
    parts = cleaned.split()
    result = {"full_name": cleaned, "name": cleaned}
    if len(parts) == 1:
        result["last_name"] = parts[0].title()
    else:
        result["first_name"] = parts[0].title()
        result["last_name"] = parts[-1].title()
        if len(parts) > 2:
            result["middle_name"] = " ".join(p.title() for p in parts[1:-1])
    return result


def _parse_age(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    match = re.search(r"\d+", value)
    return match.group(0) if match else value.strip()


def _booking_date_from_match(match: re.Match[str]) -> str:
    raw = match.group(3)
    return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"
