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

        originals: List[Dict[str, Any]] = [
            r for r in (records or []) if isinstance(r, dict)
        ]
        prepared = [dict(r) for r in originals]
        for rec in prepared:
            classify_record(rec)
        total = len(prepared)
        skipped = 0
        kept_pairs: List[tuple[Dict[str, Any], Dict[str, Any]]] = []
        if skip_existing_urls:
            existing = self.existing_source_urls()
            for original, rec in zip(originals, prepared):
                url = (rec.get("source_url") or rec.get("source_id") or "").strip()
                if url and url in existing:
                    skipped += 1
                    continue
                if url:
                    existing.add(url)
                kept_pairs.append((original, rec))
        else:
            kept_pairs = list(zip(originals, prepared))

        imported = 0
        if not kept_pairs:
            pass
        elif len(kept_pairs) == 1:
            # Single-row path returns id onto the caller's dict (GUI live import).
            original, rec = kept_pairs[0]
            for key in ("charge_category", "likely_ethnicity", "name_confidence"):
                if key in rec:
                    original[key] = rec[key]
            rid = self.insert_arrest(rec)
            original["id"] = int(rid)
            imported = 1
        else:
            for original, rec in kept_pairs:
                for key in ("charge_category", "likely_ethnicity", "name_confidence"):
                    if key in rec:
                        original[key] = rec[key]
            imported = self.insert_arrests_batch([rec for _, rec in kept_pairs])
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
