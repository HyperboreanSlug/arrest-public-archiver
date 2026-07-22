"""San Francisco Sheriff inmate search monitor."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from scraper.city_monitors.base import CityMonitor, CityMonitorInfo
from scraper.state_bulk.common import clean, normalize_race, normalize_sex, raw_json

SOURCE = "sf_sheriff"
STATE = "CA"
SEARCH_URL = "https://www.sfsheriff.gov/inmate-search"


class SFSheriffMonitor(CityMonitor):
    info = CityMonitorInfo(
        id=SOURCE,
        label="San Francisco Sheriff",
        city="San Francisco",
        state=STATE,
        search_url=SEARCH_URL,
    )

    def search(self, last_name: str = "", first_name: str = "") -> List[Dict[str, Any]]:
        if not last_name:
            return []
        try:
            resp = self._post(SEARCH_URL, data={
                "last_name": last_name,
                "first_name": first_name,
            })
            resp.raise_for_status()
        except Exception:
            return []
        return self._parse_results(resp.text)

    def _parse_results(self, html: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        rows = soup.select("table tr")[1:]
        out: List[Dict[str, Any]] = []
        for row in rows:
            cells = [td.get_text(strip=True) for td in row.select("td")]
            if len(cells) < 3:
                continue
            rec = self._map_row(cells)
            if rec:
                out.append(rec)
        return out

    def _map_row(self, cells: List[str]) -> Optional[Dict[str, Any]]:
        name = clean(cells[0]) if cells else None
        if not name:
            return None
        parts = name.split(",", 1)
        last = parts[0].strip().title()
        first = parts[1].strip().title() if len(parts) > 1 else None
        booking_date = clean(cells[1]) if len(cells) > 1 else None
        charge = clean(cells[2]) if len(cells) > 2 else None
        housing = clean(cells[3]) if len(cells) > 3 else None
        return {
            "first_name": first,
            "last_name": last,
            "full_name": name.title(),
            "booking_date": booking_date,
            "arrest_date": booking_date,
            "charge_description": charge,
            "agency": housing or "SF Sheriff",
            "jurisdiction": "San Francisco Sheriff",
            "state": STATE,
            "county": "San Francisco",
            "source_id": f"sf_sheriff:{name}:{booking_date}",
            "source_url": SEARCH_URL,
            "source_system": SOURCE,
            "raw_json": raw_json({"cells": cells[:5]}),
        }
