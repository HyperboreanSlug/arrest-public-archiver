"""Discovery helpers for Busted Newspaper state and county listing pages."""

from __future__ import annotations

import re
from typing import List, Set, Tuple
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .client import BustedNewspaperClient

BASE_URL = "https://bustednewspaper.com"
_STATE_PATH = re.compile(r"^/mugshots/([a-z0-9-]+)/?$", re.IGNORECASE)
_COUNTY_PATH = re.compile(
    r"^/mugshots/([a-z0-9-]+)/([a-z0-9-]+)/?$",
    re.IGNORECASE,
)


def _links(html: str, base_url: str = BASE_URL) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    from urllib.parse import urljoin

    return [
        urljoin(base_url, href)
        for link in soup.select("a[href]")
        if (href := link.get("href"))
    ]


def discover_states(html: str, base_url: str = BASE_URL) -> List[str]:
    """Return sorted state slugs linked from a Busted Newspaper page."""
    states: Set[str] = set()
    for link in _links(html, base_url):
        match = _STATE_PATH.match(urlparse(link).path)
        if match:
            states.add(match.group(1).lower())
    return sorted(states)


def discover_counties(html: str, state: str, base_url: str = BASE_URL) -> List[str]:
    """Return sorted county slugs linked from a state page."""
    wanted_state = state.strip().lower()
    counties: Set[str] = set()
    for link in _links(html, base_url):
        match = _COUNTY_PATH.match(urlparse(link).path)
        if match and match.group(1).lower() == wanted_state:
            counties.add(match.group(2).lower())
    return sorted(counties)


def discover_states_from_homepage(client: BustedNewspaperClient) -> List[str]:
    return discover_states(client.get(BASE_URL))


def discover_counties_for_state(client: BustedNewspaperClient, state: str) -> List[str]:
    state = state.strip().lower()
    return discover_counties(client.get(f"{BASE_URL}/mugshots/{state}/"), state)


def county_page_url(state: str, county: str, page: int = 1) -> str:
    """Build a county listing URL, including pagination when ``page`` > 1."""
    state = state.strip().lower()
    county = county.strip().lower()
    base = f"{BASE_URL}/mugshots/{state}/{county}/"
    if page <= 1:
        return base
    return f"{base}page/{page}/"


def iter_counties(client: BustedNewspaperClient) -> List[Tuple[str, str]]:
    """Return sorted ``(state_slug, county_slug)`` pairs from the site index."""
    pairs: List[Tuple[str, str]] = []
    for state in discover_states_from_homepage(client):
        for county in discover_counties_for_state(client, state):
            pairs.append((state, county))
    return pairs
