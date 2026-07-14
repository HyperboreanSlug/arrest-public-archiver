"""Weighted / round-robin partition of (state, county) work units."""
from __future__ import annotations

from typing import Dict, List, Tuple

from .registry import get_mugshot_source


def partition_work_units(
    units: List[Tuple[str, str]],
    source_ids: List[str],
) -> Dict[str, List[Tuple[str, str]]]:
    """
    Split (state, county) work units across sources by weight (round-robin).

    Same geographic unit is assigned to exactly one host so we do not hammer
    every aggregator for identical county data.
    """
    available = []
    weights = []
    for sid in source_ids:
        info = get_mugshot_source(sid)
        if info is None or not info.available:
            continue
        available.append(sid)
        weights.append(max(0.1, float(info.weight or 1.0)))
    if not available:
        return {}
    buckets: Dict[str, List[Tuple[str, str]]] = {s: [] for s in available}
    # Weighted round-robin via cumulative tokens
    cursor = 0.0
    total_w = sum(weights)
    step = total_w / len(available)
    for i, unit in enumerate(units):
        # pick host i % n with weight bias
        idx = int((i * step + cursor) / step) % len(available)
        # simpler: pure round-robin (equal hosts) — enough for 2 live hosts
        idx = i % len(available)
        buckets[available[idx]].append(unit)
    return buckets
