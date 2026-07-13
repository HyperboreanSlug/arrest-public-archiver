"""Polite HTTP client for RecentlyBooked public pages."""

from __future__ import annotations

import time
from typing import Optional

import requests

from ..config import DEFAULT_DELAY, MAX_RETRIES, REQUEST_TIMEOUT, USER_AGENT


class RecentlyBookedClient:
    """Small retrying client which spaces requests by at least ``delay`` seconds."""

    def __init__(
        self,
        delay: float = DEFAULT_DELAY,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.delay = max(0.0, delay)
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
        self._last_request_at: Optional[float] = None

    def _wait_for_rate_limit(self) -> None:
        if self._last_request_at is None:
            return
        remaining = self.delay - (time.monotonic() - self._last_request_at)
        if remaining > 0:
            time.sleep(remaining)

    def get(self, url: str) -> str:
        """Fetch *url* and return decoded response text, retrying transient failures."""
        return self._request(url).text

    def get_bytes(self, url: str) -> bytes:
        """Fetch *url* and return response bytes (used for booking photos)."""
        return self._request(url).content

    def _request(self, url: str) -> requests.Response:
        """Fetch *url* and return the response after rate limiting and retries."""
        last_error: Optional[requests.RequestException] = None
        for attempt in range(MAX_RETRIES):
            self._wait_for_rate_limit()
            try:
                response = self.session.get(url, timeout=REQUEST_TIMEOUT)
                self._last_request_at = time.monotonic()
                response.raise_for_status()
                # Prefer UTF-8 when the body starts with a UTF-8 BOM or XML decl.
                raw = response.content[:4]
                if raw.startswith(b"\xef\xbb\xbf") or raw.lstrip().startswith(b"<?xml"):
                    response.encoding = "utf-8"
                return response
            except requests.RequestException as exc:
                last_error = exc
                if attempt + 1 == MAX_RETRIES:
                    raise
                time.sleep(self.delay * (attempt + 1))
        raise last_error  # pragma: no cover

    def close(self) -> None:
        """Release the underlying HTTP connection pool."""
        self.session.close()
