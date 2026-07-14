"""Result container for multi-source scrape runs."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class MultiSourceResult:
    records: List[Dict[str, Any]] = field(default_factory=list)
    by_source: Dict[str, int] = field(default_factory=dict)
    errors: Dict[str, str] = field(default_factory=dict)
    skipped_identity: int = 0
