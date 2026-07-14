"""High-level scraper for the public RecentlyBooked listings."""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Set

from .client import RecentlyBookedClient
from .locked_set import LockedURLSet, _LockedURLSet
from .scraper_process import RecentlyBookedProcessMixin
from .scraper_scrape import RecentlyBookedScrapeMixin

CancelCheck = Callable[[], bool]
ProgressCallback = Callable[[int, Optional[int]], None]
RecordCallback = Callable[[Dict[str, Any], int], None]


class RecentlyBookedScraper(RecentlyBookedScrapeMixin, RecentlyBookedProcessMixin):
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
    def _as_url_set(urls: Optional[Set[str]]) -> LockedURLSet:
        if isinstance(urls, LockedURLSet):
            return urls
        return LockedURLSet(urls)


__all__ = ["RecentlyBookedScraper", "LockedURLSet", "_LockedURLSet"]
