"""Photo archival helpers for RecentlyBooked records."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Optional

from .client import RecentlyBookedClient


def download_photo(
    record: Mapping[str, Any],
    client: Optional[RecentlyBookedClient] = None,
    output_root: Path | str = Path("data/photos/recentlybooked"),
) -> Optional[Path]:
    """Download a record's photo and return its archive path, or ``None`` if absent."""
    photo_url = record.get("photo_url")
    state = str(record.get("state") or "").lower()
    county = str(record.get("county") or "").lower()
    booking_id = str(record.get("booking_id") or record.get("source_id") or "").strip()
    if not photo_url or not state or not county or not booking_id:
        return None

    destination = Path(output_root) / state / county / f"{booking_id}.webp"
    if destination.exists():
        return destination
    own_client = client is None
    client = client or RecentlyBookedClient()
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(client.get_bytes(str(photo_url)))
        return destination
    finally:
        if own_client:
            client.close()
