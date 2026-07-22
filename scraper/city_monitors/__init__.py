"""City jail monitors — custom scrapers for cities not on RB/Mugshots.com."""
from __future__ import annotations

from scraper.city_monitors.registry import CITY_MONITORS, get_city_monitor, list_city_monitors

__all__ = ["CITY_MONITORS", "get_city_monitor", "list_city_monitors"]
