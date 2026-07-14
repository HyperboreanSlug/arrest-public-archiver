"""Fixed-size pool of rate-limited HTTP clients (one client ≈ one thread).

Each borrowed client keeps its own last-request clock, so ``delay`` is enforced
**per thread** rather than globally across all concurrent workers.
"""
from __future__ import annotations

import queue
from typing import Callable, Generic, Iterable, List, Optional, TypeVar

T = TypeVar("T")


class ClientPool(Generic[T]):
    """Borrow/release pool; size should match the worker thread count."""

    def __init__(self, factory: Callable[[], T], size: int) -> None:
        n = max(1, int(size))
        self._q: queue.Queue[T] = queue.Queue(maxsize=n)
        self._all: List[T] = []
        for _ in range(n):
            client = factory()
            self._all.append(client)
            self._q.put(client)

    def borrow(self, timeout: Optional[float] = None) -> T:
        return self._q.get(timeout=timeout)

    def release(self, client: T) -> None:
        self._q.put(client)

    def close(self) -> None:
        """Close all pooled clients (best-effort)."""
        # Drain queue so nothing is in-flight conceptually.
        leftover: List[T] = []
        while True:
            try:
                leftover.append(self._q.get_nowait())
            except queue.Empty:
                break
        for client in self._all:
            closer = getattr(client, "close", None)
            if callable(closer):
                try:
                    closer()
                except Exception:
                    pass

    def __enter__(self) -> "ClientPool[T]":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
