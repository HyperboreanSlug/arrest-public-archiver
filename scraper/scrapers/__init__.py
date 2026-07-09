"""Arrest open-data scrapers."""

from .base import BaseScraper, ScraperFactory
from .socrata import SocrataScraper
from .direct_download import DirectDownloadScraper

__all__ = [
    "BaseScraper",
    "ScraperFactory",
    "SocrataScraper",
    "DirectDownloadScraper",
]
