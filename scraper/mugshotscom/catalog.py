"""Discovery helpers for mugshots.com state / county indexes."""

from __future__ import annotations

import re
from typing import List, Set, Tuple
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .client import MugshotsComClient

BASE_URL = "https://mugshots.com"
_STATE_PATH = re.compile(r"^/US-States/([A-Za-z-]+)/?$", re.I)
_COUNTY_PATH = re.compile(
    r"^/US-States/([A-Za-z-]+)/([A-Za-z0-9-]+-County-[A-Z]{2})/?$",
    re.I,
)
_DETAIL_PATH = re.compile(
    r"^/US-States/([A-Za-z-]+)/([A-Za-z0-9-]+)/([^/]+)\.(\d+)\.html$",
    re.I,
)
_LIVE_DETAIL = re.compile(
    r"^/Current-Events/([^/]+)\.(\d+)\.html$",
    re.I,
)

# Full state name (site slug) → USPS code
STATE_SLUG_TO_CODE = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "district-of-columbia": "DC",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new-hampshire": "NH",
    "new-jersey": "NJ",
    "new-mexico": "NM",
    "new-york": "NY",
    "north-carolina": "NC",
    "north-dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode-island": "RI",
    "south-carolina": "SC",
    "south-dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west-virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
}
CODE_TO_STATE_SLUG = {v: k for k, v in STATE_SLUG_TO_CODE.items()}


def state_code_from_slug(slug: str) -> str:
    key = (slug or "").strip().lower()
    return STATE_SLUG_TO_CODE.get(key, key.upper()[:2] if key else "")


def state_slug_from_code(code: str) -> str:
    key = (code or "").strip().upper()
    if key in CODE_TO_STATE_SLUG:
        return CODE_TO_STATE_SLUG[key]
    # Allow full slug already
    low = (code or "").strip().lower()
    if low in STATE_SLUG_TO_CODE:
        return low
    return low


def normalize_county_slug(slug: str) -> str:
    """``Alachua-County-FL`` → ``alachua``."""
    value = (slug or "").strip()
    value = re.sub(r"-County-[A-Z]{2}$", "", value, flags=re.I)
    value = value.replace("-", " ").strip().lower()
    return value


def discover_states(html: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    found: Set[str] = set()
    for a in soup.select("a[href]"):
        href = a.get("href") or ""
        path = urlparse(urljoin(BASE_URL, href)).path
        m = _STATE_PATH.match(path)
        if m:
            slug = m.group(1)
            if slug.lower() not in ("us-states",):
                found.add(slug)
    return sorted(found, key=str.lower)


def discover_counties(html: str, state_slug: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    want = state_slug.strip()
    found: Set[str] = set()
    for a in soup.select("a[href]"):
        href = a.get("href") or ""
        path = urlparse(urljoin(BASE_URL, href)).path
        m = _COUNTY_PATH.match(path)
        if m and m.group(1).lower() == want.lower():
            found.add(m.group(2))
    return sorted(found)


def discover_states_from_site(client: MugshotsComClient) -> List[str]:
    return discover_states(client.get(f"{BASE_URL}/US-States/"))


def discover_counties_for_state(
    client: MugshotsComClient, state: str
) -> List[str]:
    slug = state_slug_from_code(state)
    return discover_counties(
        client.get(f"{BASE_URL}/US-States/{slug}/"),
        slug,
    )


def county_page_url(state: str, county_slug: str, page: int = 1) -> str:
    slug = state_slug_from_code(state)
    county = county_slug.strip()
    # Accept bare county name or full Alachua-County-FL form
    if not re.search(r"-County-[A-Z]{2}$", county, re.I):
        code = state_code_from_slug(slug)
        bits = "-".join(p.capitalize() for p in county.replace("_", "-").split("-"))
        county = f"{bits}-County-{code}"
    base = f"{BASE_URL}/US-States/{slug}/{county}/"
    if page <= 1:
        return base
    return f"{base}?page={page}"


def detail_urls_from_listing(html: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    out: List[str] = []
    seen: Set[str] = set()
    for a in soup.select("a[href]"):
        href = a.get("href") or ""
        path = urlparse(urljoin(BASE_URL, href)).path
        if _DETAIL_PATH.match(path) or _LIVE_DETAIL.match(path):
            full = urljoin(BASE_URL, path)
            if full not in seen:
                seen.add(full)
                out.append(full)
    return out


def iter_counties(client: MugshotsComClient) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []
    for state in discover_states_from_site(client):
        for county in discover_counties_for_state(client, state):
            pairs.append((state, county))
    return pairs
