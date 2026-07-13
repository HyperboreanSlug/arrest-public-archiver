"""High-level scraper for the public RecentlyBooked listings."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
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


class _LockedURLSet:
    """Thread-safe URL set used to skip already-seen booking pages."""

    def __init__(self, initial: Optional[Set[str]] = None) -> None:
        self._urls: Set[str] = set(initial or ())
        self._lock = threading.Lock()

    def __contains__(self, url: object) -> bool:
        with self._lock:
            return url in self._urls

    def add(self, url: str) -> None:
        with self._lock:
            self._urls.add(url)

    def snapshot(self) -> Set[str]:
        with self._lock:
            return set(self._urls)


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
        self.delay = float(self.client.delay)

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

    @staticmethod
    def _as_url_set(urls: Optional[Set[str]]) -> _LockedURLSet:
        if isinstance(urls, _LockedURLSet):
            return urls
        return _LockedURLSet(urls)

    def _process_record(
        self,
        record: Dict[str, Any],
        *,
        import_details: bool,
        with_photos: bool,
        with_html: bool,
        client: Optional[RecentlyBookedClient] = None,
    ) -> Dict[str, Any]:
        """Enrich one listing card. Network/archive failures are recorded, not raised."""
        http = client or self.client
        try:
            if import_details or with_html:
                detail_html = http.get(str(record["source_url"]))
                if import_details:
                    record.update(parse_detail(detail_html, str(record["source_url"])))
                if with_html:
                    html_path = archive_html(detail_html, record)
                    if html_path:
                        record["html_path"] = str(html_path)
            if with_photos:
                photo_path = download_photo(record, http)
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
        workers: int = 1,
    ) -> List[Dict[str, Any]]:
        """Scrape a county; zero ``max_pages`` continues until a page has no cards."""
        state, county = state.strip().lower(), county.strip().lower()
        known_urls = self._as_url_set(skip_existing_urls)
        workers = max(1, int(workers or 1))
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
            fresh: List[Dict[str, Any]] = []
            for card in cards:
                if self._cancelled(cancel_check):
                    return records
                source_url = str(card["source_url"])
                if source_url in known_urls:
                    continue
                known_urls.add(source_url)
                fresh.append(card)
            if not fresh:
                page += 1
                continue
            if workers == 1:
                for card in fresh:
                    if self._cancelled(cancel_check):
                        return records
                    done = self._process_record(
                        card,
                        import_details=True,
                        with_photos=with_photos,
                        with_html=with_html,
                    )
                    records.append(done)
                    self._emit(record_cb, done, len(records))
                    self._report(progress_cb, len(records))
            else:
                self._process_cards_parallel(
                    fresh,
                    workers=workers,
                    with_photos=with_photos,
                    with_html=with_html,
                    cancel_check=cancel_check,
                    progress_cb=progress_cb,
                    record_cb=record_cb,
                    records=records,
                )
            page += 1
        return records

    def _process_cards_parallel(
        self,
        cards: List[Dict[str, Any]],
        *,
        workers: int,
        with_photos: bool,
        with_html: bool,
        cancel_check: Optional[CancelCheck],
        progress_cb: Optional[ProgressCallback],
        record_cb: Optional[RecordCallback],
        records: List[Dict[str, Any]],
    ) -> None:
        """Fetch detail/photo for many cards concurrently (one HTTP client per worker)."""
        lock = threading.Lock()

        def job(card: Dict[str, Any]) -> Dict[str, Any]:
            if self._cancelled(cancel_check):
                return dict(card)
            with RecentlyBookedClient(delay=self.delay) as http:
                return self._process_record(
                    dict(card),
                    import_details=True,
                    with_photos=with_photos,
                    with_html=with_html,
                    client=http,
                )

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(job, card) for card in cards]
            for fut in as_completed(futures):
                if self._cancelled(cancel_check):
                    for pending in futures:
                        pending.cancel()
                    break
                try:
                    done = fut.result()
                except Exception as exc:
                    done = {"scrape_error": f"{type(exc).__name__}: {exc}"}
                with lock:
                    records.append(done)
                    count = len(records)
                self._emit(record_cb, done, count)
                self._report(progress_cb, count)

    def _scrape_counties_parallel(
        self,
        counties: List[tuple[str, str]],
        *,
        workers: int,
        max_pages: int,
        known_urls: _LockedURLSet,
        with_photos: bool,
        with_html: bool,
        cancel_check: Optional[CancelCheck],
        progress_cb: Optional[ProgressCallback],
        record_cb: Optional[RecordCallback],
    ) -> List[Dict[str, Any]]:
        """Scrape many counties concurrently; each county uses its own HTTP client."""
        records: List[Dict[str, Any]] = []
        total = 0
        lock = threading.Lock()

        def forward(rec: Dict[str, Any], _n: int) -> None:
            nonlocal total
            with lock:
                total += 1
                count = total
                records.append(rec)
            self._emit(record_cb, rec, count)
            self._report(progress_cb, count)

        def job(pair: tuple[str, str]) -> None:
            if self._cancelled(cancel_check):
                return
            state, county = pair
            with RecentlyBookedScraper(delay=self.delay) as local:
                local.scrape_county(
                    state,
                    county,
                    max_pages=max_pages,
                    skip_existing_urls=known_urls,
                    with_photos=with_photos,
                    with_html=with_html,
                    cancel_check=cancel_check,
                    record_cb=forward,
                    workers=1,  # avoid nested pools
                )

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(job, pair) for pair in counties]
            for fut in as_completed(futures):
                if self._cancelled(cancel_check):
                    for pending in futures:
                        pending.cancel()
                    break
                try:
                    fut.result()
                except Exception:
                    pass
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
        workers: int = 1,
    ) -> List[Dict[str, Any]]:
        """Discover and scrape every county listed for a state."""
        known_urls = self._as_url_set(skip_existing_urls)
        workers = max(1, int(workers or 1))
        counties = [
            (state, county)
            for county in discover_counties_for_state(self.client, state)
        ]
        if workers == 1:
            records: List[Dict[str, Any]] = []
            total = 0

            def _forward(rec: Dict[str, Any], _county_n: int) -> None:
                nonlocal total
                total += 1
                records.append(rec)
                self._emit(record_cb, rec, total)
                self._report(progress_cb, total)

            for _state, county in counties:
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
                    workers=1,
                )
            return records
        return self._scrape_counties_parallel(
            counties,
            workers=workers,
            max_pages=max_pages,
            known_urls=known_urls,
            with_photos=with_photos,
            with_html=with_html,
            cancel_check=cancel_check,
            progress_cb=progress_cb,
            record_cb=record_cb,
        )

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
        workers: int = 1,
    ) -> List[Dict[str, Any]]:
        """Discover all counties and scrape them, respecting an optional county cap."""
        known_urls = self._as_url_set(skip_existing_urls)
        workers = max(1, int(workers or 1))
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
        if limit_counties:
            counties = counties[: int(limit_counties)]
        if workers == 1:
            records: List[Dict[str, Any]] = []
            total = 0

            def _forward(rec: Dict[str, Any], _county_n: int) -> None:
                nonlocal total
                total += 1
                records.append(rec)
                self._emit(record_cb, rec, total)
                self._report(progress_cb, total)

            for state, county in counties:
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
                    workers=1,
                )
            return records
        return self._scrape_counties_parallel(
            counties,
            workers=workers,
            max_pages=max_pages,
            known_urls=known_urls,
            with_photos=with_photos,
            with_html=with_html,
            cancel_check=cancel_check,
            progress_cb=progress_cb,
            record_cb=record_cb,
        )
