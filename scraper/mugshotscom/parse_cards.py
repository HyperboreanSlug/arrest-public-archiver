"""Listing / live-feed card parsers for mugshots.com."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .catalog import (
    BASE_URL,
    _DETAIL_PATH,
    _LIVE_DETAIL,
    normalize_county_slug,
    state_code_from_slug,
)


def _text(tag) -> Optional[str]:
    if tag is None:
        return None
    value = tag.get_text(" ", strip=True)
    return value or None


def parse_listing_cards(html: str, *, state_slug: str = "", county_slug: str = "") -> List[Dict[str, Any]]:
    """Extract listing card stubs (url + name + photo) from a county page."""
    soup = BeautifulSoup(html, "html.parser")
    cards: List[Dict[str, Any]] = []
    seen = set()
    for a in soup.select("a[href]"):
        href = a.get("href") or ""
        full = urljoin(BASE_URL, href)
        path = urlparse(full).path
        m = _DETAIL_PATH.match(path)
        if not m:
            continue
        if full in seen:
            continue
        seen.add(full)
        name = _text(a) or ""
        img = a.select_one("img[alt], img[src]")
        if img and img.get("alt"):
            name = str(img.get("alt")).strip() or name
        photo = None
        if img and img.get("src") and "mugshot" in str(img.get("src")).lower():
            photo = urljoin(BASE_URL, str(img.get("src")))
        rec: Dict[str, Any] = {
            "source_url": full,
            "source_system": "mugshotscom",
            "source_id": m.group(4),
            "state": state_code_from_slug(m.group(1) or state_slug),
            "county": normalize_county_slug(m.group(2) or county_slug),
            "full_name": name or None,
        }
        if photo:
            rec["photo_url"] = photo
        if name:
            parts = name.replace(",", " ").split()
            if len(parts) >= 2:
                rec["first_name"] = parts[0]
                rec["last_name"] = parts[-1]
                if len(parts) > 2:
                    rec["middle_name"] = " ".join(parts[1:-1])
        cards.append(rec)
    return cards


def parse_live_feed(html: str) -> List[Dict[str, Any]]:
    """Homepage cards — prefer real county booking pages over news posts."""
    soup = BeautifulSoup(html, "html.parser")
    county_cards: List[Dict[str, Any]] = []
    news_cards: List[Dict[str, Any]] = []
    seen = set()
    for a in soup.select("a[href]"):
        href = a.get("href") or ""
        full = urljoin(BASE_URL, href)
        path = urlparse(full).path
        m_county = _DETAIL_PATH.match(path)
        m_news = _LIVE_DETAIL.match(path)
        if not m_county and not m_news:
            continue
        if full in seen:
            continue
        seen.add(full)
        name = _text(a) or ""
        img = a.find("img")
        if img and img.get("alt"):
            name = str(img.get("alt")).strip() or name
        if m_news and (":" in name or len(name) > 60):
            continue
        rec: Dict[str, Any] = {
            "source_url": full,
            "source_system": "mugshotscom",
            "full_name": name or None,
        }
        if m_county:
            rec["source_id"] = m_county.group(4)
            rec["state"] = state_code_from_slug(m_county.group(1))
            rec["county"] = normalize_county_slug(m_county.group(2))
            if img and img.get("src") and "mugshot" in str(img.get("src")).lower():
                rec["photo_url"] = urljoin(BASE_URL, str(img.get("src")))
            county_cards.append(rec)
        else:
            rec["source_id"] = m_news.group(2)
            if img and img.get("src") and "mugshot" in str(img.get("src")).lower():
                rec["photo_url"] = urljoin(BASE_URL, str(img.get("src")))
                news_cards.append(rec)
    return county_cards + news_cards
