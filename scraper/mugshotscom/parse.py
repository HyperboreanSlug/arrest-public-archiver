"""HTML parsers for mugshots.com listing and detail pages."""
from __future__ import annotations

from .parse_cards import parse_listing_cards, parse_live_feed
from .parse_detail import parse_detail

__all__ = [
    "parse_detail",
    "parse_listing_cards",
    "parse_live_feed",
]
