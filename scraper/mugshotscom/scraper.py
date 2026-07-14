"""High-level scraper for mugshots.com public listings."""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from .client import MugshotsComClient
from .locked_set import LockedURLSet, _LockedURLSet
from .scraper_county import MugshotsComCountyMixin
from .scraper_enrich import MugshotsComEnrichMixin

CancelCheck = Callable[[], bool]
ProgressCallback = Callable[[int, Optional[int]], None]
RecordCallback = Callable[[Dict[str, Any], int], None]


class MugshotsComScraper(MugshotsComCountyMixin, MugshotsComEnrichMixin):
    """Collect mugshots.com county listings with polite pacing."""

    def __init__(
        self,
        client: Optional[MugshotsComClient] = None,
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

            self.client = MugshotsComClient(
                delay=float(delay) if delay is not None else DEFAULT_DELAY
            )
            self._owns_client = True
        self.delay = float(self.client.delay)

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> "MugshotsComScraper":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    @staticmethod
    def _cancelled(cancel_check: Optional[CancelCheck]) -> bool:
        return bool(cancel_check and cancel_check())


__all__ = ["MugshotsComScraper", "LockedURLSet", "_LockedURLSet"]
