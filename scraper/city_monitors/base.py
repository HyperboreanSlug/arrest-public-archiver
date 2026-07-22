"""Base class for city jail booking monitors."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import requests

from scraper.config_types import USER_AGENT


@dataclass
class CityMonitorInfo:
    id: str
    label: str
    city: str
    state: str
    search_url: str
    available: bool = True
    notes: str = ""


class CityMonitor:
    """Base for HTML-form-based city jail booking scrapers."""

    info: CityMonitorInfo

    def __init__(self, delay: float = 2.0):
        self._session = requests.Session()
        self._session.headers["User-Agent"] = USER_AGENT
        self._delay = delay
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def _get(self, url: str, **kw) -> requests.Response:
        time.sleep(self._delay)
        return self._session.get(url, timeout=30, **kw)

    def _post(self, url: str, data: dict, **kw) -> requests.Response:
        time.sleep(self._delay)
        return self._session.post(url, data=data, timeout=30, **kw)

    def search(self, last_name: str = "", first_name: str = "") -> List[Dict[str, Any]]:
        raise NotImplementedError

    def fetch_recent(self, limit: int = 100) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def map_record(self, raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError
