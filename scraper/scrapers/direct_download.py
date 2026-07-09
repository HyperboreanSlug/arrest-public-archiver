"""Direct CSV/JSON bulk download for arrest sources."""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Dict, List

from ..config import ArrestSource, DEFAULT_DELAY
from ..normalize import apply_field_map, stamp_source
from .base import BaseScraper


class DirectDownloadScraper(BaseScraper):
    def __init__(self, source: ArrestSource, delay: float = DEFAULT_DELAY):
        super().__init__(source, delay=delay)
        if not source.direct_downloads:
            raise ValueError(f"{source.id}: no direct_downloads URLs")

    def scrape(self, row_limit: int = 0) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        cap = int(row_limit or self.source.default_row_limit or 0)
        for url in self.source.direct_downloads:
            if cap and len(out) >= cap:
                break
            resp = self._request(url)
            ctype = (resp.headers.get("Content-Type") or "").lower()
            text = resp.text
            rows: List[Dict[str, Any]] = []
            if "json" in ctype or text.lstrip().startswith("[") or text.lstrip().startswith("{"):
                data = resp.json()
                if isinstance(data, list):
                    rows = [r for r in data if isinstance(r, dict)]
                elif isinstance(data, dict):
                    for key in ("data", "records", "results", "features"):
                        if isinstance(data.get(key), list):
                            rows = [r for r in data[key] if isinstance(r, dict)]
                            break
            else:
                reader = csv.DictReader(io.StringIO(text))
                rows = [dict(r) for r in reader]
            for row in rows:
                if cap and len(out) >= cap:
                    break
                rec = apply_field_map(row, self.source.field_map)
                rec = stamp_source(
                    rec,
                    source_id=self.source.id,
                    state=self.source.state,
                    jurisdiction=self.source.jurisdiction,
                )
                out.append(rec)
        return out
