"""High-level scraper for Busted Newspaper county listings."""
from __future__ import annotations

from .scraper_core import BustedNewspaperScraperBase, CancelCheck, ProgressCallback
from .scraper_run import BustedNewspaperScraperRun


class BustedNewspaperScraper(BustedNewspaperScraperBase, BustedNewspaperScraperRun):
    """Collect Busted Newspaper county listing pages with conservative pacing."""


__all__ = [
    "BustedNewspaperScraper",
    "CancelCheck",
    "ProgressCallback",
]
