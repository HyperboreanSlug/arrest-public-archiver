"""
Configuration for public arrest / booking open-data sources.

Primary product goal: archive published arrest records and flag ethnic
surname vs recorded-race mismatches (misclassification analysis).

scrape_method:
  - socrata:   Socrata SODA API / CSV export (domain + dataset_id)
  - direct:    published bulk CSV/JSON URL(s)
  - interactive: search-only or no automated bulk path
  - stats_only: aggregates only (not person-level browse)

Mugshot HTML scrapers (RecentlyBooked, Busted Newspaper) live under the
RecentlyBooked GUI tab / ``python -m scraper recentlybooked`` — not here.
"""
from __future__ import annotations

from typing import List, Optional

from scraper.config_sources import SOURCES
from scraper.config_types import (
    DEFAULT_DELAY,
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    USER_AGENT,
    ArrestSource,
)


def get_source(source_id: str) -> Optional[ArrestSource]:
    sid = (source_id or "").strip().lower()
    for s in SOURCES:
        if s.id.lower() == sid:
            return s
    return None


def get_bulk_sources() -> List[ArrestSource]:
    return [
        s
        for s in SOURCES
        if s.scrape_method in ("socrata", "direct") and s.status == "verified_bulk"
    ]


def get_named_sources() -> List[ArrestSource]:
    """Sources most useful for surname/race misclassification (publish names)."""
    return [s for s in get_bulk_sources() if s.has_names]


__all__ = [
    "USER_AGENT",
    "DEFAULT_DELAY",
    "MAX_RETRIES",
    "REQUEST_TIMEOUT",
    "ArrestSource",
    "SOURCES",
    "get_source",
    "get_bulk_sources",
    "get_named_sources",
]
