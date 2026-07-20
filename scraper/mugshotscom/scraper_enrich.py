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
        client=None,
    ) -> Dict[str, Any]:
        http = client or self.client
        try:
            html = http.get(
                str(record["source_url"]),
                referer=str(record.get("referer") or BASE_URL + "/"),
            )
            record.update(parse_detail(html, str(record["source_url"])))
            if with_photos:
                path = download_photo(record, http)
                if path:
                    record["photo_path"] = str(path)
            classify_record(record)
        except Exception as exc:
            record["scrape_error"] = f"{type(exc).__name__}: {exc}"
        return record

    def _enrich_batch_parallel(
        self,
        batch: List[Dict[str, Any]],
        *,
        workers: int,
        with_photos: bool,
        records: List[Dict[str, Any]],
        lock,
        row_limit: int = 0,
        cancel_check=None,
        record_cb=None,
        progress_cb=None,
    ) -> None:
        """Enrich cards with one rate-limited client per worker (delay/thread)."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        from ..client_pool import ClientPool
        from .client import MugshotsComClient

        client_pool = ClientPool(
            lambda: MugshotsComClient(delay=self.delay), max(1, workers)
        )

        def work(card: Dict[str, Any]) -> Dict[str, Any]:
            http = client_pool.borrow()
            try:
                return self._enrich(card, with_photos=with_photos, client=http)
            finally:
                client_pool.release(http)

        try:
            pool = ThreadPoolExecutor(max_workers=max(1, workers))
            try:
                futures = [pool.submit(work, c) for c in batch]
                for fut in as_completed(futures):
                    if self._cancelled(cancel_check):
                        break
                    try:
                        done = fut.result()
                    except Exception as exc:
                        done = {
                            "scrape_error": str(exc),
                            "source_system": "mugshotscom",
                        }
                    with lock:
                        if row_limit and len(records) >= row_limit:
                            break
                        records.append(done)
                        n = len(records)
                    if record_cb:
                        record_cb(done, n)
                    if progress_cb:
                        progress_cb(n, row_limit or None)
            finally:
                pool.shutdown(wait=False, cancel_futures=True)
        finally:
            client_pool.close()

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
