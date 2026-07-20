"""Live-feed scraping across mugshot hosts."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, Optional, Set, Tuple

from .types import CancelCheck, ProgressCallback, RecordCallback
from .result import MultiSourceResult


class LiveScrapeMixin:
    """Parallel live-feed scrape for each selected source."""

    def scrape_live(
        self,
        *,
        row_limit_per_source: int = 20,
        skip_existing_urls: Optional[Set[str]] = None,
        with_photos: bool = True,
        cancel_check: Optional[CancelCheck] = None,
        record_cb: Optional[RecordCallback] = None,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> MultiSourceResult:
        """Poll each available source's live feed in parallel."""
        result = MultiSourceResult()
        if skip_existing_urls:
            for u in skip_existing_urls:
                self.identity.add_url(u)
        wrapped, skipped_fn = self._wrap_record_cb(record_cb, skip_identity=True)

        def run_one(sid: str) -> Tuple[str, int, Optional[str]]:
            try:
                n = self._live_one(
                    sid,
                    row_limit=row_limit_per_source,
                    with_photos=with_photos,
                    cancel_check=cancel_check,
                    record_cb=wrapped,
                    progress_cb=progress_cb,
                )
                return sid, n, None
            except Exception as exc:
                return sid, 0, str(exc)

        workers = max(1, min(len(self.source_ids), 4))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = [pool.submit(run_one, sid) for sid in self.source_ids]
            for fut in as_completed(futs):
                sid, n, err = fut.result()
                result.by_source[sid] = n
                if err:
                    result.errors[sid] = err
        result.skipped_identity = skipped_fn()
        result.records = []  # records delivered via callback
        return result

    def _live_one(
        self,
        source_id: str,
        *,
        row_limit: int,
        with_photos: bool,
        cancel_check: Optional[CancelCheck],
        record_cb: Optional[RecordCallback],
        progress_cb: Optional[ProgressCallback],
    ) -> int:
        known = {u.casefold() for u in self.identity.snapshot_urls()}
        count = [0]

        def cb(rec: Dict[str, Any], n: int) -> None:
            count[0] = n
            if record_cb:
                record_cb(rec, n)

        if source_id == "recentlybooked":
            from scraper.recentlybooked import RecentlyBookedScraper
            from scraper.recentlybooked.client import RecentlyBookedClient
            from scraper.recentlybooked.live_feed import fetch_live_feed

            with RecentlyBookedClient(delay=self.delay) as client:
                cards = fetch_live_feed(client, import_details=False)
                with RecentlyBookedScraper(client=client) as s:
                    for card in cards[: max(1, row_limit * 3)]:
                        if cancel_check and cancel_check():
                            break
                        url = str(card.get("source_url") or "")
                        if not url or url.casefold() in known:
                            continue
                        done = s._process_record(
                            dict(card),
                            import_details=True,
                            with_photos=with_photos,
                            with_html=False,
                        )
                        done.setdefault("source_system", "recentlybooked")
                        cb(done, count[0] + 1)
                        if count[0] >= row_limit:
                            break
            return count[0]

        if source_id == "mugshotscom":
            from scraper.mugshotscom import MugshotsComScraper

            with MugshotsComScraper(delay=self.delay) as s:
                s.scrape_live(
                    row_limit=row_limit,
                    skip_existing_urls=known,
                    with_photos=with_photos,
                    cancel_check=cancel_check,
                    record_cb=cb,
                    progress_cb=progress_cb,
                )
            return count[0]

        if source_id == "bustednewspaper":
            from scraper.bustednewspaper import (
                BN_SSL_OUTAGE_MSG,
                BustedNewspaperScraper,
                BustedNewspaperUnavailable,
            )

            try:
                with BustedNewspaperScraper(delay=max(1.0, self.delay)) as s:
                    s.scrape_live(
                        row_limit=row_limit,
                        skip_existing_urls=known,
                        with_photos=with_photos,
                        cancel_check=cancel_check,
                        record_cb=cb,
                    )
            except BustedNewspaperUnavailable as exc:
                raise RuntimeError(str(exc) or BN_SSL_OUTAGE_MSG) from exc
            return count[0]

        raise RuntimeError(f"No live-feed implementation for source {source_id!r}")
