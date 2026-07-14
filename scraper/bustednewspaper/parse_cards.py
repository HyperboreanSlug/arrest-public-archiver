"""County listing card parser for Busted Newspaper."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from .parse_util import (
    BASE_URL,
    _COUNTY_PATH,
    _booking_date_from_match,
    _detail_match,
    _name_parts,
    _text,
    normalize_county_slug,
    state_code_from_slug,
)


def _record_from_card(
    card: Tag,
    *,
    state_slug: Optional[str] = None,
    county_slug: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    link = card.select_one("a.image-link[href], h2 a[href], .content a[href]")
    if link is None or not link.get("href"):
        return None
    source_url = urljoin(BASE_URL, str(link.get("href")))
    match = _detail_match(source_url)
    if match is None:
        return None
    state_slug = (state_slug or match.group(1)).lower()
    county_link = card.select_one(".cat-title a[href]")
    if county_link and county_link.get("href"):
        county_match = _COUNTY_PATH.match(urlparse(str(county_link.get("href"))).path)
        if county_match:
            county_slug = county_match.group(2).lower()
    name = _text(card.select_one("h2 a, h2")) or link.get("title")
    if name and "|" in name:
        name = name.split("|", 1)[0].strip()
    record: Dict[str, Any] = {
        **_name_parts(name),
        "state": state_code_from_slug(state_slug),
        "source_url": source_url.rstrip("/") + "/",
        "source_id": f"{match.group(2)}/{match.group(3)}",
        "source_system": "bustednewspaper",
        "booking_date": _booking_date_from_match(match),
    }
    if county_slug:
        record["county"] = normalize_county_slug(county_slug)
        record["jurisdiction"] = record["county"].replace("-", " ").title()
    image = card.select_one("img.image[src], img.wp-post-image[src], a.image-link img[src]")
    if image and image.get("src"):
        record["photo_url"] = urljoin(BASE_URL, str(image.get("src")))
    return record


def parse_county_cards(
    html: str,
    *,
    state_slug: Optional[str] = None,
    county_slug: Optional[str] = None,
    base_url: str = BASE_URL,
) -> List[Dict[str, Any]]:
    """Parse booking cards from a county listing page."""
    soup = BeautifulSoup(html, "html.parser")
    cards: Iterable[Tag] = soup.select("article.post, .posts-list article")
    records: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for card in cards:
        record = _record_from_card(
            card,
            state_slug=state_slug,
            county_slug=county_slug,
        )
        if record and record["source_url"] not in seen:
            seen.add(record["source_url"])
            records.append(record)
    return records
