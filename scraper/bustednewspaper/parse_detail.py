"""Detail-page parser for Busted Newspaper."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .parse_util import (
    _COUNTY_PATH,
    _LABEL_ALIASES,
    _booking_date_from_match,
    _detail_match,
    _name_parts,
    _parse_age,
    _text,
    normalize_county_slug,
    state_code_from_slug,
)


def _detail_pairs(soup: BeautifulSoup) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for dt in soup.select("dl dt"):
        label = _text(dt)
        dd = dt.find_next_sibling("dd")
        value = _text(dd)
        if not label or not value:
            continue
        field = _LABEL_ALIASES.get(label.strip().lower())
        if field:
            values[field] = value
    return values


def _parse_charges(soup: BeautifulSoup) -> Optional[str]:
    charges: List[str] = []
    for item in soup.select("ul.charges li, .charges li"):
        text = item.get_text(" ", strip=True)
        if text:
            charges.append(text)
    if charges:
        return "; ".join(charges)
    return None


def _county_from_breadcrumb(soup: BeautifulSoup) -> Optional[str]:
    for link in soup.select(".fbc-items a[href], .breadcrumbs a[href]"):
        match = _COUNTY_PATH.match(urlparse(str(link.get("href") or "")).path)
        if match:
            return normalize_county_slug(match.group(2))
    return None


def _photo_from_detail(soup: BeautifulSoup, source_url: str) -> Optional[str]:
    image = soup.select_one(
        ".featured-image img[src], .page-header-image-single img[src], "
        "article img.attachment-full[src], img.wp-post-image[src]"
    )
    if image and image.get("src"):
        return urljoin(source_url, str(image.get("src")))
    meta = soup.select_one('meta[property="og:image"][content]')
    if meta:
        return str(meta.get("content") or "").strip() or None
    return None


def parse_detail(html: str, source_url: str) -> Dict[str, Any]:
    """Parse a booking detail page into a canonical record dictionary."""
    match = _detail_match(source_url)
    record: Dict[str, Any] = {
        "source_url": source_url.rstrip("/") + "/",
        "source_system": "bustednewspaper",
    }
    if match:
        state_slug = match.group(1).lower()
        name_slug = match.group(2)
        booking_key = match.group(3)
        record.update(
            {
                "state": state_code_from_slug(state_slug),
                "source_id": f"{name_slug}/{booking_key}",
                "booking_date": _booking_date_from_match(match),
            }
        )
    soup = BeautifulSoup(html, "html.parser")
    county = _county_from_breadcrumb(soup)
    if county:
        record["county"] = county
        record["jurisdiction"] = county.replace("-", " ").title()
    h1 = _text(soup.select_one(".page-hero h1, h1"))
    if h1:
        name_line = h1.split("\n")[0].strip()
        record.update(_name_parts(name_line))
    record.update(_detail_pairs(soup))
    if record.get("age"):
        record["age"] = _parse_age(str(record["age"]))
    charges = _parse_charges(soup)
    if charges:
        record["charge_description"] = charges
    photo_url = _photo_from_detail(soup, source_url)
    if photo_url:
        record["photo_url"] = photo_url
    raw: Dict[str, Any] = {"detail_fields": _detail_pairs(soup)}
    if charges:
        raw["charges"] = charges.split("; ")
    record["raw_json"] = json.dumps(raw, ensure_ascii=False)
    return record
