"""Socrata SODA open-data scraper for arrest/booking datasets."""

from __future__ import annotations

from typing import Any, Dict, List
from urllib.parse import quote

from ..config import ArrestSource, DEFAULT_DELAY
from ..normalize import apply_field_map, stamp_source
from .base import BaseScraper


class SocrataScraper(BaseScraper):
    """
    Paginate SODA JSON API:
      https://{domain}/resource/{dataset_id}.json?$limit=N&$offset=O
    """

    def __init__(self, source: ArrestSource, delay: float = DEFAULT_DELAY):
        super().__init__(source, delay=delay)
        if not source.socrata_domain or not source.socrata_dataset_id:
            raise ValueError(f"{source.id}: missing socrata_domain/dataset_id")

    def scrape(self, row_limit: int = 0) -> List[Dict[str, Any]]:
        domain = self.source.socrata_domain.strip().rstrip("/")
        if domain.startswith("http"):
            base = domain
        else:
            base = f"https://{domain}"
        dataset = self.source.socrata_dataset_id.strip()
        page_size = 1000
        offset = 0
        cap = int(row_limit or self.source.default_row_limit or 0)
        out: List[Dict[str, Any]] = []

        while True:
            if cap and len(out) >= cap:
                break
            take = page_size
            if cap:
                take = min(page_size, cap - len(out))
            url = (
                f"{base}/resource/{quote(dataset)}.json"
                f"?$limit={take}&$offset={offset}"
            )
            resp = self._request(url)
            batch = resp.json()
            if not isinstance(batch, list) or not batch:
                break
            for row in batch:
                if not isinstance(row, dict):
                    continue
                rec = apply_field_map(row, self.source.field_map)
                rec = stamp_source(
                    rec,
                    source_id=self.source.id,
                    state=self.source.state,
                    jurisdiction=self.source.jurisdiction,
                )
                # keep a compact raw snapshot for debugging field maps
                rec.setdefault("raw_json", None)
                out.append(rec)
            if len(batch) < take:
                break
            offset += len(batch)
        return out
