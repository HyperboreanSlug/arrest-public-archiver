"""Base scraper + factory for arrest open-data sources."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from ..config import (
    USER_AGENT,
    DEFAULT_DELAY,
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    ArrestSource,
    get_source,
    SOURCES,
)


class BaseScraper(ABC):
    def __init__(self, source: ArrestSource, delay: float = DEFAULT_DELAY):
        self.source = source
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "application/json,text/csv,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )

    def _request(self, url: str, method: str = "GET", **kwargs) -> requests.Response:
        headers = kwargs.pop("headers", None)
        merged = dict(self.session.headers)
        if headers:
            merged.update(headers)
        kwargs.setdefault("timeout", REQUEST_TIMEOUT)
        last_exc: Optional[BaseException] = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = self.session.request(method, url, headers=merged, **kwargs)
                resp.raise_for_status()
                time.sleep(self.delay)
                return resp
            except requests.RequestException as e:
                last_exc = e
                if attempt == MAX_RETRIES - 1:
                    raise
                time.sleep(self.delay * (attempt + 1))
        raise last_exc  # pragma: no cover

    @abstractmethod
    def scrape(self, row_limit: int = 0) -> List[Dict[str, Any]]:
        ...

    def scrape_to_file(
        self,
        output_dir: Path,
        filename: Optional[str] = None,
        row_limit: int = 0,
    ) -> Path:
        import csv

        records = self.scrape(row_limit=row_limit)
        if not records:
            return Path()
        output_dir.mkdir(parents=True, exist_ok=True)
        dest = output_dir / (filename or f"{self.source.id}.csv")
        fields: List[str] = []
        seen = set()
        for rec in records:
            for k in rec:
                if k not in seen:
                    seen.add(k)
                    fields.append(k)
        with open(dest, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(records)
        return dest

    def close(self) -> None:
        try:
            self.session.close()
        except Exception:
            pass


class ScraperFactory:
    @staticmethod
    def create(source_id: str, delay: float = DEFAULT_DELAY) -> BaseScraper:
        src = get_source(source_id)
        if not src:
            raise ValueError(f"Unknown source id: {source_id}")
        method = (src.scrape_method or "").lower()
        if method == "socrata":
            from .socrata import SocrataScraper

            return SocrataScraper(src, delay=delay)
        if method == "direct":
            from .direct_download import DirectDownloadScraper

            return DirectDownloadScraper(src, delay=delay)
        raise ValueError(
            f"Source {source_id} method={method!r} is not bulk-scrapeable "
            f"(status={src.status})."
        )

    @staticmethod
    def list_sources() -> List[ArrestSource]:
        return list(SOURCES)
