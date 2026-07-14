"""Enrich and live-feed scrape helpers for mugshots.com."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from ..charge_classifications import classify_record
from .catalog import BASE_URL, county_page_url
from .locked_set import LockedURLSet
from .parse import parse_detail, parse_listing_cards, parse_live_feed
from .photos import download_photo


class MugshotsComEnrichMixin:
    def _enrich(
        self,
        record: Dict[str, Any],
        *,
        with_photos: bool = True,
    ) -> Dict[str, Any]:
        try:
            html = self.client.get(
                str(record["source_url"]),
                referer=str(record.get("referer") or BASE_URL + "/"),
            )
            record.update(parse_detail(html, str(record["source_url"])))
            if with_photos:
                path = download_photo(record, self.client)
                if path:
                    record["photo_path"] = str(path)
            classify_record(record)
        except Exception as exc:
            record["scrape_error"] = f"{type(exc).__name__}: {exc}"
        return record

    def scrape_live(
        self,
        *,
        row_limit: int = 30,
        skip_existing_urls: Optional[Set[str]] = None,
        with_photos: bool = True,
        cancel_check=None,
        record_cb=None,
        progress_cb=None,
    ) -> List[Dict[str, Any]]:
        known = LockedURLSet(skip_existing_urls)
        records: List[Dict[str, Any]] = []
        try:
            cards = parse_live_feed(self.client.get(BASE_URL + "/"))
        except Exception:
            cards = []
        if len(cards) < max(3, row_limit // 2):
            try:
                from .catalog import discover_counties_for_state

                counties = discover_counties_for_state(self.client, "florida")[:2]
                for co in counties:
                    html = self.client.get(
                        county_page_url("florida", co),
                        referer=f"{BASE_URL}/US-States/Florida/",
                    )
                    cards.extend(
                        parse_listing_cards(html, state_slug="Florida", county_slug=co)
                    )
            except Exception:
                pass
        for card in cards:
            if self._cancelled(cancel_check):
                break
            if row_limit and len(records) >= row_limit:
                break
            url = str(card.get("source_url") or "")
            if not url or url in known:
                continue
            known.add(url)
            done = self._enrich(dict(card), with_photos=with_photos)
            if not (
                done.get("last_name")
                or done.get("first_name")
                or done.get("race")
                or done.get("photo_path")
            ):
                continue
            records.append(done)
            if record_cb:
                record_cb(done, len(records))
            if progress_cb:
                progress_cb(len(records), row_limit or None)
        return records
