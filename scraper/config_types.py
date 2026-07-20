"""Arrest source dataclass and HTTP defaults."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

USER_AGENT = (
    "ArrestPublicArchiver/0.1 (public open-data research; polite rate limits)"
)
DEFAULT_DELAY = 1.0
MAX_RETRIES = 3
REQUEST_TIMEOUT = 60


@dataclass
class ArrestSource:
    """One open-data or bulk arrest/booking feed."""

    id: str
    name: str
    state: str
    jurisdiction: str  # city / county / state agency label
    scrape_method: str = "interactive"
    # Socrata
    socrata_domain: Optional[str] = None
    socrata_dataset_id: Optional[str] = None
    # Direct bulk
    direct_downloads: List[str] = field(default_factory=list)
    portal_url: Optional[str] = None
    # Map source column names → canonical arrest fields
    field_map: Dict[str, str] = field(default_factory=dict)
    # Cap rows for polite first-run tests (0 = unlimited)
    default_row_limit: int = 0
    status: str = "verified_bulk"  # verified_bulk | interactive | stats_only | broken
    notes: str = ""
    # True when published rows typically include a personal name
    has_names: bool = True
