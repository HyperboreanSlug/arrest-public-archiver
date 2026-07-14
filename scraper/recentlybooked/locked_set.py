"""Thread-safe URL set used to skip already-seen booking pages."""
from __future__ import annotations

import threading
from typing import Optional, Set


class LockedURLSet:
    def __init__(self, initial: Optional[Set[str]] = None) -> None:
        self._urls: Set[str] = set(initial or ())
        self._lock = threading.Lock()

    def __contains__(self, url: object) -> bool:
        with self._lock:
            return url in self._urls

    def add(self, url: str) -> None:
        with self._lock:
            self._urls.add(url)

    def snapshot(self) -> Set[str]:
        with self._lock:
            return set(self._urls)


# Back-compat private alias
_LockedURLSet = LockedURLSet
