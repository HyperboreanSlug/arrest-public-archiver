"""Detail-page parser for mugshots.com."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .catalog import (
    BASE_URL,
    _DETAIL_PATH,
    _LIVE_DETAIL,
    normalize_county_slug,
    state_code_from_slug,
)
from .parse_charges import charges_from_soup

_FIELD_MAP = {
    "last name": "last_name",
    "first name": "first_name",
    "middle name": "middle_name",
    "race": "race",
    "sex": "sex",
    "gender": "sex",
    "age": "age",
    "booking date": "booking_date",
    "arrest date": "arrest_date",
    "agency": "agency",
    "height": "height",
    "weight": "weight",
    "hair": "hair",
    "eyes": "eyes",
    "mni #": "source_id",
    "mugshots.com": "source_id",
}


def _text(tag) -> Optional[str]:
    if tag is None:
        return None
    value = tag.get_text(" ", strip=True)
    return value or None


def _parse_booking_datetime(raw: str) -> Dict[str, str]:
    """``7/07/2021 at 14:39`` → booking_date + arrest_time-ish."""
    out: Dict[str, str] = {}
    s = (raw or "").strip()
    if not s:
        return out
    m = re.match(
        r"(\d{1,2})/(\d{1,2})/(\d{4})(?:\s+at\s+(\d{1,2}:\d{2}))?",
        s,
        re.I,
    )
    if m:
        mm, dd, yyyy = int(m.group(1)), int(m.group(2)), m.group(3)
        out["booking_date"] = f"{yyyy}-{mm:02d}-{dd:02d}"
        if m.group(4):
            out["arrest_time"] = m.group(4)
        return out
    out["booking_date"] = s
    return out


def parse_detail(html: str, source_url: str) -> Dict[str, Any]:
    """Parse a mugshots.com booking detail page."""
    soup = BeautifulSoup(html, "html.parser")
    path = urlparse(source_url).path
    record: Dict[str, Any] = {
        "source_url": source_url.rstrip("/") if not source_url.endswith(".html") else source_url,
        "source_system": "mugshotscom",
    }
    m = _DETAIL_PATH.match(path) or _LIVE_DETAIL.match(path)
    if m and _DETAIL_PATH.match(path):
        state_slug = m.group(1)
        county_part = m.group(2)
        source_id = m.group(4)
        record["state"] = state_code_from_slug(state_slug)
        record["county"] = normalize_county_slug(county_part)
        record["jurisdiction"] = record["county"].replace("-", " ").title()
        record["source_id"] = source_id
    elif m and _LIVE_DETAIL.match(path):
        record["source_id"] = m.group(2)

    for field in soup.select(".field"):
        name = (_text(field.select_one(".name")) or "").strip().lower().rstrip(":")
        val = _text(field.select_one(".value"))
        if not name or not val:
            continue
        key = _FIELD_MAP.get(name)
        if not key:
            continue
        if key == "booking_date":
            record.update(_parse_booking_datetime(val))
        elif key == "age":
            digits = re.sub(r"\D", "", val)
            if digits:
                try:
                    record["age"] = int(digits)
                except ValueError:
                    record["age"] = val
        else:
            record[key] = val

    first = str(record.get("first_name") or "").strip()
    middle = str(record.get("middle_name") or "").strip()
    last = str(record.get("last_name") or "").strip()
    if first or last:
        record["full_name"] = " ".join(p for p in (first, middle, last) if p)

    charges = charges_from_soup(soup)
    if charges:
        record["charge_description"] = charges

    if not record.get("agency"):
        for tr in soup.select("table tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) >= 2 and cells[0].lower() == "agency":
                record["agency"] = cells[1]
                break

    crumb = soup.get_text(" ", strip=True)
    m_c = re.search(r"booked in\s+([A-Za-z .'-]+ County),\s*([A-Z]{2})", crumb)
    if m_c:
        record.setdefault("county", m_c.group(1).replace(" County", "").strip().lower())
        record.setdefault("state", m_c.group(2).upper())
        record.setdefault("jurisdiction", m_c.group(1).strip())

    meta = soup.select_one('meta[property="og:image"][content]')
    if meta and meta.get("content"):
        record["photo_url"] = str(meta.get("content")).strip()
    else:
        img = soup.select_one("img.hidden-narrow[src], img[src*='thumbs.mugshots.com']")
        if img and img.get("src"):
            record["photo_url"] = urljoin(BASE_URL, str(img.get("src")))

    raw = {
        "fields": {
            (_text(f.select_one(".name")) or ""): (_text(f.select_one(".value")) or "")
            for f in soup.select(".field")
            if f.select_one(".name")
        }
    }
    record["raw_json"] = json.dumps(raw, ensure_ascii=False)
    return record
