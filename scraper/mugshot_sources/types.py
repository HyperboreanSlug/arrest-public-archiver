"""Shared callback type aliases for multi-source orchestration."""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

CancelCheck = Callable[[], bool]
ProgressCallback = Callable[[int, Optional[int]], None]
RecordCallback = Callable[[Dict[str, Any], int], None]
