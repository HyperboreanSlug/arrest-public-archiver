"""Multi-host mugshot scrape orchestrator (live + balanced mixins)."""
from __future__ import annotations

import threading
from typing import Any, Callable, Dict, List, Optional, Tuple

from .balanced import BalancedScrapeMixin
from .geo import GeoScrapeMixin
from .identity import IdentityIndex
from .live import LiveScrapeMixin
from .registry import MugshotSourceInfo, get_mugshot_source, list_mugshot_sources
from .types import RecordCallback


class MultiSourceOrchestrator(
    LiveScrapeMixin,
    BalancedScrapeMixin,
    GeoScrapeMixin,
):
    """Run live / county scrapes across multiple mugshot hosts in parallel."""

    def __init__(
        self,
        source_ids: Optional[List[str]] = None,
        *,
        delay: float = 1.0,
        identity: Optional[IdentityIndex] = None,
    ) -> None:
        ids = source_ids or [s.id for s in list_mugshot_sources(available_only=True)]
        self.source_ids = [
            sid
            for sid in ids
            if (
                get_mugshot_source(sid) or MugshotSourceInfo(sid, sid, "", False)
            ).available
        ]
        self.delay = max(0.0, float(delay))
        self.identity = identity or IdentityIndex()
        self._count_lock = threading.Lock()
        self._total = 0

    def _wrap_record_cb(
        self,
        record_cb: Optional[RecordCallback],
        *,
        skip_identity: bool = True,
    ) -> Tuple[RecordCallback, Callable[[], int]]:
        skipped = [0]

        def wrapped(rec: Dict[str, Any], _n: int) -> None:
            if skip_identity and not self.identity.claim_record(rec):
                with self._count_lock:
                    skipped[0] += 1
                return
            with self._count_lock:
                self._total += 1
                n = self._total
            if record_cb:
                record_cb(rec, n)

        return wrapped, lambda: skipped[0]
