"""ScraperFactory adapter for Busted Newspaper."""

from __future__ import annotations

from typing import Any, Dict, List

from ..bustednewspaper.scraper import BustedNewspaperScraper
from ..config import ArrestSource, DEFAULT_DELAY
from .base import BaseScraper


class BustedNewspaperOpenDataScraper(BaseScraper):
    """Adapter exposing Busted Newspaper through the open-data Scrape tab."""

    def scrape(self, row_limit: int = 0) -> List[Dict[str, Any]]:
        cap = int(row_limit or self.source.default_row_limit or 0)
        with BustedNewspaperScraper(delay=self.delay) as scraper:
            return scraper.scrape(row_limit=cap, with_photos=True)
