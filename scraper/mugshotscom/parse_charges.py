"""Extract charge/offense text from mugshots.com detail HTML."""
from __future__ import annotations

import re
from typing import List, Optional

from bs4 import BeautifulSoup

from scraper.charge_sanitize import is_non_charge, sanitize_charge_text


def _text(tag) -> Optional[str]:
    if tag is None:
        return None
    value = tag.get_text(" ", strip=True)
    return value or None


def charges_from_soup(soup: BeautifulSoup) -> Optional[str]:
    """Collect real offense text; never treat state names as charges."""
    charges: List[str] = []
    offense_fields = {
        "offense",
        "offenses",
        "crime",
        "crimes",
        "crime information",
        "charge",
        "charges",
        "description",
    }
    for tr in soup.select("table tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) >= 2 and cells[0].lower().rstrip(":") in (
            "description",
            "charge",
            "charges",
            "offense",
            "offenses",
        ):
            charges.append(cells[1])
    for field in soup.select(".field"):
        name = (_text(field.select_one(".name")) or "").strip().lower().rstrip(":")
        val = _text(field.select_one(".value")) or ""
        if name in offense_fields and val:
            charges.append(val)
            continue
        if "charge" in name:
            val = val or field.get_text(" ", strip=True)
            m = re.search(
                r"Description\s*([A-Z0-9].+?)(?:Case Number|Agency|$)",
                val or "",
            )
            if m:
                charges.append(m.group(1).strip())
            elif val and val.lower() not in ("charge number", "charges:"):
                charges.append(val)
    # H1 is often "Name - State"; never treat a state name as a charge.
    h1 = _text(soup.select_one("h1#item-title, h1"))
    if h1 and " - " in h1:
        tail = h1.split(" - ", 1)[1]
        tail = re.sub(r"\s*-\s*[A-Za-z ]+$", "", tail).strip()
        if tail and len(tail) > 3 and not is_non_charge(tail):
            charges.append(tail)
    seen = set()
    out: List[str] = []
    for c in charges:
        cleaned = sanitize_charge_text(c) if c else ""
        if not cleaned or is_non_charge(cleaned):
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
    return "; ".join(out) if out else None
