"""NYC DOC Inmate Lookup Service monitor."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from scraper.city_monitors.base import CityMonitor, CityMonitorInfo
from scraper.state_bulk.common import clean, normalize_race, normalize_sex, raw_json

SOURCE = "nyc_doc"
STATE = "NY"
SEARCH_URL = "https://a073-ilsweb.nyc.gov/"

RACE_CODES = {
    "B": "Black", "BLACK": "Black",
    "W": "White", "WHITE": "White",
    "H": "Hispanic", "HISPANIC": "Hispanic",
    "A": "Asian", "ASIAN": "Asian",
    "I": "American Indian", "AMERICAN INDIAN": "American Indian",
    "O": "Other", "OTHER": "Other",
    "U": None, "UNKNOWN": None,
}


class NYCDocMonitor(CityMonitor):
    info = CityMonitorInfo(
        id=SOURCE,
        label="NYC DOC Inmate Lookup",
        city="New York City",
        state=STATE,
        search_url=SEARCH_URL,
    )

    def search(self, last_name: str = "", first_name: str = "") -> List[Dict[str, Any]]:
        if not last_name:
            return []
        try:
            resp = self._post(SEARCH_URL, data={
                "lastname": last_name,
                "firstname": first_name,
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
            if len(cells) < 4:
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
        nysid = clean(cells[1]) if len(cells) > 1 else None
        race_raw = clean(cells[2]) if len(cells) > 2 else None
        race = RACE_CODES.get((race_raw or "").upper(), race_raw)
        charge = clean(cells[3]) if len(cells) > 3 else None
        facility = clean(cells[4]) if len(cells) > 4 else None
        admit = clean(cells[5]) if len(cells) > 5 else None
        return {
            "first_name": first,
            "last_name": last,
            "full_name": name.title(),
            "race": race,
            "booking_date": admit,
            "arrest_date": admit,
            "charge_description": charge,
            "agency": facility or "NYC DOC",
            "jurisdiction": "NYC Department of Correction",
            "state": STATE,
            "county": "New York",
            "booking_id": nysid,
            "source_id": f"nyc_doc:{nysid or name}",
            "source_url": SEARCH_URL,
            "source_system": SOURCE,
            "raw_json": raw_json({"nysid": nysid, "cells": cells[:6]}),
        }
