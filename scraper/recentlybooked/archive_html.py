"""HTML archival helpers for RecentlyBooked records."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Optional
from urllib.parse import urlparse


def archive_html(
    html: str,
    record: Mapping[str, Any],
    output_root: Path | str = Path("data/html/recentlybooked"),
) -> Optional[Path]:
    """Save a detail page using its URL slug and return the saved path."""
    state = str(record.get("state") or "").lower()
    county = str(record.get("county") or "").lower()
    source_url = str(record.get("source_url") or "")
    slug = urlparse(source_url).path.rstrip("/").rsplit("/", 1)[-1]
    if not state or not county or not slug:
        return None
    destination = Path(output_root) / state / county / f"{slug}.html"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(html, encoding="utf-8")
    return destination
