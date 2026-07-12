"""RecentlyBooked homepage feed collection."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .catalog import BASE_URL
from .client import RecentlyBookedClient
from .parse import parse_detail, parse_live_feed


def fetch_live_feed(
    client: Optional[RecentlyBookedClient] = None,
    import_details: bool = True,
) -> List[Dict[str, Any]]:
    """Fetch the homepage and optionally enrich each listing with its detail page."""
    own_client = client is None
    client = client or RecentlyBookedClient()
    try:
        records = parse_live_feed(client.get(BASE_URL))
        if not import_details:
            return records
        for record in records:
            source_url = str(record["source_url"])
            record.update(parse_detail(client.get(source_url), source_url))
        return records
    finally:
        if own_client:
            client.close()
