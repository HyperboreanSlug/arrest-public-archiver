"""High-level scraper for the public RecentlyBooked listings."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set

from ..charge_classifications import classify_record
from .archive_html import archive_html
from .catalog import (
    BASE_URL,
    discover_counties_for_state,
    discover_counties_from_sitemap,
    discover_states_from_homepage,
)
from .client import RecentlyBookedClient
from .parse import parse_county_cards, parse_detail
from .photos import download_photo

CancelCheck = Callable[[], bool]
ProgressCallback = Callable[[int, Optional[int]], None]
RecordCallback = Callable[[Dict[str, Any], int], None]


class RecentlyBookedScraper:
    """Collect RecentlyBooked public listing pages with conservative request pacing."""

    def __init__(
        self,
        client: Optional[RecentlyBookedClient] = None,
        *,
        delay: Optional[float] = None,
    ) -> None:
        if client is not None:
            self.client = client
            self._owns_client = False
            if delay is not None:
                self.client.delay = max(0.0, float(delay))
        else:
            from ..config import DEFAULT_DELAY

            self.client = RecentlyBookedClient(
                delay=float(delay) if delay is not None else DEFAULT_DELAY
            )
            self._owns_client = True

    def close(self) -> None:
        """Close an internally-created HTTP client."""
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> "RecentlyBookedScraper":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    @staticmethod
    def _cancelled(cancel_check: Optional[CancelCheck]) -> bool:
        return bool(cancel_check and cancel_check())

    @staticmethod
    def _report(progress_cb: Optional[ProgressCallback], count: int) -> None:
        if progress_cb:
            progress_cb(count, None)

    @staticmethod
    def _emit(
        record_cb: Optional[RecordCallback],
        record: Dict[str, Any],
        count: int,
    ) -> None:
        if record_cb:
            record_cb(record, count)

    def _process_record(
        self,
        record: Dict[str, Any],
        *,
        import_details: bool,
        with_photos: bool,
        with_html: bool,
    ) -> Dict[str, Any]:
        """Enrich one listing card. Network/archive failures are recorded, not raised."""
        try:
            if import_details or with_html:
                detail_html = self.client.get(str(record["source_url"]))
                if import_details:
                    record.update(parse_detail(detail_html, str(record["source_url"])))
                if with_html:
                    html_path = archive_html(detail_html, record)
                    if html_path:
                        record["html_path"] = str(html_path)
            if with_photos:
                photo_path = download_photo(record, self.client)
                if photo_path:
                    record["photo_path"] = str(photo_path)
            classify_record(record)
        except Exception as exc:
            record["scrape_error"] = f"{type(exc).__name__}: {exc}"
        return record

    def scrape_live(
        self,
        import_details: bool = True,
        with_photos: bool = True,
        with_html: bool = True,
        progress_cb: Optional[ProgressCallback] = None,
        record_cb: Optional[RecordCallback] = None,
    ) -> List[Dict[str, Any]]:
        """Scrape current homepage cards and optionally archive their detail data."""
        from .live_feed import fetch_live_feed

        records = fetch_live_feed(self.client, import_details=False)
        output: List[Dict[str, Any]] = []
        for record in records:
            done = self._process_record(
                record,
                import_details=import_details,
                with_photos=with_photos,
                with_html=with_html,
            )
            output.append(done)
            self._emit(record_cb, done, len(output))
            self._report(progress_cb, len(output))
        return output

    def scrape_county(
        self,
        state: str,
        county: str,
        max_pages: int = 0,
        skip_existing_urls: Optional[Set[str]] = None,
        with_photos: bool = True,
        with_html: bool = True,
        cancel_check: Optional[CancelCheck] = None,
        progress_cb: Optional[ProgressCallback] = None,
        record_cb: Optional[RecordCallback] = None,
    ) -> List[Dict[str, Any]]:
        """Scrape a county; zero ``max_pages`` continues until a page has no cards."""
        state, county = state.strip().lower(), county.strip().lower()
        known_urls = skip_existing_urls if skip_existing_urls is not None else set()
        records: List[Dict[str, Any]] = []
        page = 1
        while not max_pages or page <= max_pages:
            if self._cancelled(cancel_check):
                break
            page_url = f"{BASE_URL}/{state}/{county}"
            if page > 1:
                page_url += f"?p={page}"
            cards = parse_county_cards(self.client.get(page_url))
            if not cards:
                break
            for card in cards:
                if self._cancelled(cancel_check):
                    return records
                source_url = str(card["source_url"])
                if source_url in known_urls:
                    continue
                known_urls.add(source_url)
                done = self._process_record(
                    card,
                    import_details=True,
                    with_photos=with_photos,
                    with_html=with_html,
                )
                records.append(done)
                self._emit(record_cb, done, len(records))
                self._report(progress_cb, len(records))
            page += 1
        return records

    def scrape_state(
        self,
        state: str,
        max_pages: int = 0,
        skip_existing_urls: Optional[Set[str]] = None,
        with_photos: bool = True,
        with_html: bool = True,
        cancel_check: Optional[CancelCheck] = None,
        progress_cb: Optional[ProgressCallback] = None,
        record_cb: Optional[RecordCallback] = None,
    ) -> List[Dict[str, Any]]:
        """Discover and scrape every county listed for a state."""
        records: List[Dict[str, Any]] = []
        known_urls = skip_existing_urls if skip_existing_urls is not None else set()
        total = 0

        def _forward(rec: Dict[str, Any], _county_n: int) -> None:
            nonlocal total
            total += 1
            records.append(rec)
            self._emit(record_cb, rec, total)
            self._report(progress_cb, total)

        for county in discover_counties_for_state(self.client, state):
            if self._cancelled(cancel_check):
                break
            self.scrape_county(
                state,
                county,
                max_pages=max_pages,
                skip_existing_urls=known_urls,
                with_photos=with_photos,
                with_html=with_html,
                cancel_check=cancel_check,
                record_cb=_forward,
            )
        return records

    def scrape_all(
        self,
        limit_counties: int = 0,
        max_pages: int = 0,
        skip_existing_urls: Optional[Set[str]] = None,
        with_photos: bool = True,
        with_html: bool = True,
        cancel_check: Optional[CancelCheck] = None,
        progress_cb: Optional[ProgressCallback] = None,
        record_cb: Optional[RecordCallback] = None,
    ) -> List[Dict[str, Any]]:
        """Discover all counties and scrape them, respecting an optional county cap."""
        known_urls = skip_existing_urls if skip_existing_urls is not None else set()
        counties: List[tuple[str, str]] = []
        try:
            counties = list(discover_counties_from_sitemap(self.client))
        except Exception:
            counties = []
        if not counties:
            for state in discover_states_from_homepage(self.client):
                counties.extend(
                    (state, county)
                    for county in discover_counties_for_state(self.client, state)
                )
        records: List[Dict[str, Any]] = []
        total = 0

        def _forward(rec: Dict[str, Any], _county_n: int) -> None:
            nonlocal total
            total += 1
            records.append(rec)
            self._emit(record_cb, rec, total)
            self._report(progress_cb, total)

        for index, (state, county) in enumerate(counties, start=1):
            if (limit_counties and index > limit_counties) or self._cancelled(cancel_check):
                break
            self.scrape_county(
                state,
                county,
                max_pages=max_pages,
                skip_existing_urls=known_urls,
                with_photos=with_photos,
                with_html=with_html,
                cancel_check=cancel_check,
                record_cb=_forward,
            )
        return records
