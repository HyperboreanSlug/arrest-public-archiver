"""Insert / import / update arrest rows."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from scraper.database.constants import _ARREST_COLUMNS, _INSERT_SQL, _to_tuple


class InsertMixin:
    def insert_arrest(self, record: Dict[str, Any]) -> int:
        cur = self._conn.cursor()
        cur.execute(_INSERT_SQL, _to_tuple(record))
        self._conn.commit()
        return int(cur.lastrowid)

    def insert_arrests_batch(self, records: List[Dict[str, Any]]) -> int:
        if not records:
            return 0
        cur = self._conn.cursor()
        cur.executemany(_INSERT_SQL, [_to_tuple(r) for r in records])
        self._conn.commit()
        n = cur.rowcount
        return n if n is not None and n >= 0 else len(records)

    def import_records(
        self,
        records: List[Dict[str, Any]],
        *,
        skip_existing_urls: bool = True,
    ) -> Dict[str, int]:
        from scraper.charge_classifications import classify_record

        prepared = [dict(r) for r in (records or []) if isinstance(r, dict)]
        for rec in prepared:
            classify_record(rec)
        total = len(prepared)
        skipped = 0
        if skip_existing_urls:
            existing = self.existing_source_urls()
            kept = []
            for rec in prepared:
                url = (rec.get("source_url") or rec.get("source_id") or "").strip()
                if url and url in existing:
                    skipped += 1
                    continue
                if url:
                    existing.add(url)
                kept.append(rec)
            prepared = kept
        imported = self.insert_arrests_batch(prepared) if prepared else 0
        return {"imported": imported, "skipped": skipped, "total_rows": total}

    def reclassify_charges(self) -> int:
        from scraper.charge_classifications import classify_charge

        rows = self._conn.execute(
            "SELECT id, charge_description, charge_group, charge_level, "
            "charge_class, statute FROM arrests"
        ).fetchall()
        n = 0
        for row in rows:
            d = dict(row)
            cat = classify_charge(d)
            self._conn.execute(
                "UPDATE arrests SET charge_category = ? WHERE id = ?",
                (cat, d["id"]),
            )
            n += 1
        self._conn.commit()
        return n

    def update_arrest(self, row_id: int, fields: Dict[str, Any]) -> bool:
        if not fields:
            return False
        allowed = set(_ARREST_COLUMNS) | {"scraped_at"}
        cols = [k for k in fields if k in allowed]
        if not cols:
            return False
        sets = ", ".join(f"{c} = ?" for c in cols)
        vals = [fields[c] for c in cols]
        vals.append(int(row_id))
        cur = self._conn.execute(f"UPDATE arrests SET {sets} WHERE id = ?", vals)
        self._conn.commit()
        return (cur.rowcount or 0) > 0

    # SOR DeepFace UI alias
    def update_offender(self, row_id: int, fields: Dict[str, Any]) -> bool:
        return self.update_arrest(row_id, fields)
