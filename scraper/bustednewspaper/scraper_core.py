"""Core BustedNewspaperScraper init / enrich helpers."""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from ..charge_classifications import classify_record
from .client import BustedNewspaperClient
from .parse import parse_detail
from .photos import download_photo

CancelCheck = Callable[[], bool]
ProgressCallback = Callable[[int, Optional[int]], None]


class BustedNewspaperScraperBase:
    """Collect Busted Newspaper county listing pages with conservative pacing."""

    def __init__(
        self,
        client: Optional[BustedNewspaperClient] = None,
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

            self.client = BustedNewspaperClient(
                delay=float(delay) if delay is not None else DEFAULT_DELAY
            )
            self._owns_client = True
        self.delay = float(self.client.delay)

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> "BustedNewspaperScraperBase":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    @staticmethod
    def _cancelled(cancel_check: Optional[CancelCheck]) -> bool:
        return bool(cancel_check and cancel_check())

    def _enrich_record(
        self,
        record: Dict[str, Any],
        *,
        with_photos: bool = True,
    ) -> Dict[str, Any]:
        try:
            detail_html = self.client.get(str(record["source_url"]))
            record.update(parse_detail(detail_html, str(record["source_url"])))
            if with_photos:
                photo_path = download_photo(record, self.client)
                if photo_path:
                    record["photo_path"] = str(photo_path)
            classify_record(record)
        except Exception as exc:
            record["scrape_error"] = f"{type(exc).__name__}: {exc}"
        return record
