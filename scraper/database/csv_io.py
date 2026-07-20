"""CSV export helpers."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from scraper.database.constants import _ARREST_COLUMNS, _escape_like


class CsvIoMixin:
    def export_to_csv(self, output_path: str, filters: Optional[Dict[str, Any]] = None) -> int:
        import csv as csv_module

        q = "SELECT * FROM arrests WHERE 1=1"
        params: List[Any] = []
        if filters:
            if filters.get("state") and str(filters["state"]).upper() != "ALL":
                q += " AND UPPER(COALESCE(state,'')) = UPPER(?)"
                params.append(filters["state"])
            if filters.get("race"):
                q += " AND UPPER(COALESCE(race,'')) = UPPER(?)"
                params.append(filters["race"])
            if filters.get("name"):
                term = f"%{_escape_like(str(filters['name']))}%"
                q += (
                    " AND (full_name LIKE ? ESCAPE '\\' OR first_name LIKE ? ESCAPE '\\' "
                    "OR last_name LIKE ? ESCAPE '\\')"
                )
                params.extend([term, term, term])
            if filters.get("source_system"):
                q += " AND LOWER(COALESCE(source_system,'')) = LOWER(?)"
                params.append(filters["source_system"])
        rows = self._conn.execute(q, params)
        fieldnames = ["id", *_ARREST_COLUMNS, "scraped_at"]
        count = 0
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            w = csv_module.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            for row in rows:
                w.writerow(dict(row))
                count += 1
        return count
