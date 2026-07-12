"""HTML parsers for RecentlyBooked listing and detail pages."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

BASE_URL = "https://recentlybooked.com"
_DETAIL_PATH = re.compile(
    r"^/([a-z]{2})/([a-z0-9-]+)/([^/]+~([a-z0-9-]+)_([a-z0-9-]+))/?$",
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
    if len(parts) == 1:
        result["last_name"] = parts[0]
    else:
        result["first_name"] = parts[0]
        result["last_name"] = parts[-1]
        if len(parts) > 2:
            result["middle_name"] = " ".join(parts[1:-1])
    return result


def _record_from_card(card: Tag, base_url: str) -> Optional[Dict[str, Any]]:
    link = card.select_one("a.mugshot-card-link[href]") or (
        card if card.name == "a" and card.get("href") else None
    )
    if link is None:
        return None
    source_url = urljoin(base_url, str(link.get("href")))
    match = _detail_match(source_url)
    if match is None:
        return None

    name = _text(card.select_one(".mugshot-name")) or _text(link.select_one(".mugshot-name"))
    record: Dict[str, Any] = {
        **_name_parts(name),
        "state": match.group(1).upper(),
        "county": match.group(2).lower(),
        "source_url": source_url,
        "source_id": match.group(3),
        "source_system": "recentlybooked",
        "facility": match.group(4),
        "booking_id": match.group(5),
    }
    booking_date = _text(card.select_one(".mugshot-date"))
    if booking_date:
        record["booking_date"] = booking_date
    image = card.select_one("img.mugshot-image[src], .mugshot-image img[src]")
    if image:
        record["photo_url"] = urljoin(base_url, str(image.get("src")))
    else:
        record["photo_url"] = f"{BASE_URL}/images/{match.group(4)}/{match.group(5)}.webp"
    return record


def _parse_cards(html: str, base_url: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    cards: Iterable[Tag] = soup.select(".mugshot-card")
    records: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for card in cards:
        record = _record_from_card(card, base_url)
        if record and record["source_url"] not in seen:
            seen.add(record["source_url"])
            records.append(record)
    return records


def parse_live_feed(html: str, base_url: str = BASE_URL) -> List[Dict[str, Any]]:
    """Parse booking cards from the RecentlyBooked homepage."""
    return _parse_cards(html, base_url)


def parse_county_cards(html: str, base_url: str = BASE_URL) -> List[Dict[str, Any]]:
    """Parse booking cards from a county listing page."""
    return _parse_cards(html, base_url)


def _detail_pairs(soup: BeautifulSoup) -> Dict[str, str]:
    values: Dict[str, str] = {}
    containers = soup.select(".mugshot-detail, .detail-grid")
    for container in containers:
        for row in container.select("dt, .detail-row, .detail-item, li"):
            label = _text(row)
            sibling = row.find_next_sibling("dd")
            if row.name == "dt" and sibling:
                value = _text(sibling)
            else:
                label_node = row.select_one(".label, .detail-label, strong, b")
                value_node = row.select_one(".value, .detail-value")
                label = _text(label_node) or label
                value = _text(value_node)
            if not label or not value:
                continue
            normalized = re.sub(r"\s*:\s*$", "", label).strip().lower()
            field = _LABEL_ALIASES.get(normalized)
            if field:
                values[field] = value
    for label in soup.select(".mugshot-detail .label, .detail-grid .label, .detail-label"):
        value = _text(label.find_next_sibling()) or _text(label.parent.select_one(".value, .detail-value"))
        field = _LABEL_ALIASES.get(re.sub(r"\s*:\s*$", "", _text(label) or "").lower())
        if field and value:
            values[field] = value
    return values


def parse_detail(html: str, source_url: str) -> Dict[str, Any]:
    """Parse a detail page, returning a resilient canonical record dictionary."""
    match = _detail_match(source_url)
    record: Dict[str, Any] = {
        "source_url": source_url,
        "source_system": "recentlybooked",
    }
    if match:
        record.update(
            {
                "state": match.group(1).upper(),
                "county": match.group(2).lower(),
                "source_id": match.group(3),
                "facility": match.group(4),
                "booking_id": match.group(5),
                "photo_url": f"{BASE_URL}/images/{match.group(4)}/{match.group(5)}.webp",
            }
        )
    soup = BeautifulSoup(html, "html.parser")
    name = _text(soup.select_one(".mugshot-name, h1"))
    record.update(_name_parts(name))
    record.update(_detail_pairs(soup))
    image = soup.select_one("img.mugshot-image[src], .mugshot-detail img[src]")
    if image:
        record["photo_url"] = urljoin(source_url, str(image.get("src")))
    return record
