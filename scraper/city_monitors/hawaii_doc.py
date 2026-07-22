"""Hawaii DOC offender search monitor (covers Honolulu)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from scraper.city_monitors.base import CityMonitor, CityMonitorInfo
from scraper.state_bulk.common import clean, normalize_race, normalize_sex, raw_json

SOURCE = "hawaii_doc"
STATE = "HI"
SEARCH_URL = "https://corrections.ehawaii.gov/offender/search"
PHOTO_URL = "https://corrections.ehawaii.gov/offender/photo/{offender_id}"


class HawaiiDocMonitor(CityMonitor):
    info = CityMonitorInfo(
        id=SOURCE,
        label="Hawaii DOC Offender Search",
        city="Honolulu",
        state=STATE,
        search_url=SEARCH_URL,
    )

    def search(self, last_name: str = "", first_name: str = "") -> List[Dict[str, Any]]:
        if not last_name:
            return []
        try:
            resp = self._post(SEARCH_URL, data={
                "lastName": last_name,
                "firstName": first_name,
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
        offender_id = clean(cells[1]) if len(cells) > 1 else None
        facility = clean(cells[2]) if len(cells) > 2 else None
        charge = clean(cells[3]) if len(cells) > 3 else None
        admit = clean(cells[4]) if len(cells) > 4 else None
        photo_url = (
            PHOTO_URL.format(offender_id=offender_id) if offender_id else None
        )
        return {
            "first_name": first,
            "last_name": last,
            "full_name": name.title(),
            "booking_date": admit,
            "arrest_date": admit,
            "charge_description": charge,
            "agency": facility or "Hawaii DOC",
            "jurisdiction": "Hawaii DOC",
            "state": STATE,
            "county": "Honolulu",
            "booking_id": offender_id,
            "photo_url": photo_url,
            "source_id": f"hawaii_doc:{offender_id or name}",
            "source_url": SEARCH_URL,
            "source_system": SOURCE,
            "raw_json": raw_json({"offender_id": offender_id, "cells": cells[:5]}),
        }
