"""Dedupe / merge helpers for arrest rows."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from scraper.database.constants import _ARREST_COLUMNS, _MERGE_SEP, _MERGE_UNION_FIELDS


class DedupeMixin:
    # ---- Duplicates (parity with SOR: merge multi-state / multi-charge) ----

    @staticmethod
    def _row_richness(row: Dict[str, Any]) -> int:
        score = 0
        for col, weight in (
            ("race", 3),
            ("charge_description", 2),
            ("last_name", 2),
            ("first_name", 1),
            ("source_url", 2),
            ("arrest_date", 1),
            ("booking_date", 1),
            ("agency", 1),
            ("state", 1),
            ("date_of_birth", 1),
            ("address", 1),
            ("charge_category", 1),
        ):
            val = row.get(col)
            if val is not None and str(val).strip():
                score += weight
                if _MERGE_SEP in str(val):
                    score += 1
        return score

    @staticmethod
    def _split_merged_values(value: Any) -> List[str]:
        raw = str(value or "").strip()
        if not raw:
            return []
        parts: List[str] = []
        seen: set = set()
        for chunk in raw.split(_MERGE_SEP):
            for piece in re.split(r"[;\n]+", chunk):
                p = " ".join(piece.strip().split())
                if not p:
                    continue
                key = p.casefold()
                if key in seen:
                    continue
                seen.add(key)
                parts.append(p)
        return parts

    @classmethod
    def _union_field_values(cls, *values: Any) -> str:
        parts: List[str] = []
        seen: set = set()
        for v in values:
            for p in cls._split_merged_values(v):
                key = p.casefold()
                if key in seen:
                    continue
                seen.add(key)
                parts.append(p)
        return _MERGE_SEP.join(parts)

    @classmethod
    def merge_duplicate_members(
        cls,
        keep: Dict[str, Any],
        losers: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Merge losers into keep: union states/charges/URLs; fill blanks."""
        if not losers:
            return {}
        updates: Dict[str, Any] = {}
        all_rows = [keep] + list(losers)

        for col in _MERGE_UNION_FIELDS:
            merged = cls._union_field_values(*(r.get(col) for r in all_rows))
            cur = str(keep.get(col) or "").strip()
            if merged and merged != cur:
                updates[col] = merged

        for col in _ARREST_COLUMNS:
            if col in _MERGE_UNION_FIELDS or col == "flags":
                continue
            if col == "raw_json":
                cur = keep.get(col)
                if cur is not None and str(cur).strip():
                    continue
                for r in losers:
                    alt = r.get(col)
                    if alt is not None and str(alt).strip():
                        updates[col] = alt
                        break
                continue
            cur = keep.get(col)
            if cur is not None and str(cur).strip():
                continue
            for r in losers:
                alt = r.get(col)
                if alt is not None and str(alt).strip():
                    updates[col] = alt
                    break

        merged_ids = []
        for r in losers:
            try:
                merged_ids.append(int(r["id"]))
            except (KeyError, TypeError, ValueError):
                pass
        flag_out: Dict[str, Any] = {}
        raw_flags = keep.get("flags")
        if raw_flags:
            try:
                if isinstance(raw_flags, dict):
                    flag_out = dict(raw_flags)
                else:
                    flag_out = json.loads(str(raw_flags))
                    if not isinstance(flag_out, dict):
                        flag_out = {"tags": [str(raw_flags)]}
            except Exception:
                flag_out = {}
        if merged_ids:
            flag_out["merged_from_ids"] = merged_ids
            flag_out["merged_listings"] = {
                "states": cls._split_merged_values(
                    updates.get("state", keep.get("state"))
                ),
                "charges": cls._split_merged_values(
                    updates.get("charge_description", keep.get("charge_description"))
                )[:20],
                "source_urls": cls._split_merged_values(
                    updates.get("source_url", keep.get("source_url"))
                )[:20],
                "count": 1 + len(merged_ids),
            }
            try:
                updates["flags"] = json.dumps(flag_out, ensure_ascii=False, sort_keys=True)
            except Exception:
                pass
        return updates

    def find_duplicate_groups(self, strategy: str = "source_url") -> List[Dict[str, Any]]:
        s = (strategy or "source_url").lower()
        if s == "source_url":
            sql = """
                SELECT TRIM(source_url) AS dup_key, COUNT(*) AS cnt, GROUP_CONCAT(id) AS id_list
                FROM arrests
                WHERE source_url IS NOT NULL AND TRIM(source_url) != ''
                GROUP BY TRIM(source_url)
                HAVING COUNT(*) > 1
                ORDER BY cnt DESC
            """
        elif s in ("name_dob", "name_state_dob"):
            sql = """
                SELECT LOWER(TRIM(COALESCE(first_name,''))) || '|' ||
                       LOWER(TRIM(COALESCE(last_name,''))) || '|' ||
                       LOWER(TRIM(COALESCE(date_of_birth,''))) AS dup_key,
                       COUNT(*) AS cnt, GROUP_CONCAT(id) AS id_list
                FROM arrests
                WHERE last_name IS NOT NULL AND TRIM(last_name) != ''
                  AND date_of_birth IS NOT NULL AND TRIM(date_of_birth) != ''
                GROUP BY LOWER(TRIM(COALESCE(first_name,''))),
                         LOWER(TRIM(COALESCE(last_name,''))),
                         LOWER(TRIM(COALESCE(date_of_birth,'')))
                HAVING COUNT(*) > 1
                ORDER BY cnt DESC
            """
        else:
            raise ValueError(f"Unknown strategy {strategy!r}; use source_url or name_dob")

        rows = self._conn.execute(sql).fetchall()
        groups = []
        for r in rows:
            ids = [int(x) for x in str(r["id_list"] or "").split(",") if x.strip().isdigit()]
            if len(ids) < 2:
                continue
            members = []
            for rid in ids:
                rec = self.get_arrest_by_id(rid)
                if rec:
                    members.append(rec)
            if len(members) < 2:
                continue
            members.sort(
                key=lambda m: (-self._row_richness(m), int(m.get("id") or 0))
            )
            keep = members[0]
            remove_ids = [int(m["id"]) for m in members[1:]]
            groups.append({
                "strategy": s,
                "key": r["dup_key"],
                "count": len(members),
                "ids": [int(m["id"]) for m in members],
                "keep_id": int(keep["id"]),
                "remove_ids": remove_ids,
                "members": members,
            })
        return groups

    def remove_duplicates(
        self,
        strategy: str = "source_url",
        *,
        dry_run: bool = False,
        merge_fields: bool = True,
    ) -> Dict[str, Any]:
        groups = self.find_duplicate_groups(strategy)
        deleted: List[int] = []
        merged_n = 0
        kept = 0
        for g in groups:
            keep_id = int(g["keep_id"])
            remove_ids = list(g["remove_ids"])
            keep_row = self.get_arrest_by_id(keep_id)
            if not keep_row or not remove_ids:
                continue
            kept += 1
            losers = [self.get_arrest_by_id(i) for i in remove_ids]
            losers = [x for x in losers if x]
            if merge_fields and losers:
                updates = self.merge_duplicate_members(keep_row, losers)
                if updates and not dry_run:
                    self.update_arrest(keep_id, updates)
                    merged_n += len(updates)
                elif updates:
                    merged_n += len(updates)
            if not dry_run and remove_ids:
                ph = ",".join("?" for _ in remove_ids)
                self._conn.execute(
                    f"DELETE FROM arrests WHERE id IN ({ph})", remove_ids
                )
            deleted.extend(remove_ids)
        if not dry_run and deleted:
            self._conn.commit()
        return {
            "strategy": strategy,
            "dry_run": dry_run,
            "groups": kept,
            "deleted": len(deleted),
            "merged_fields": merged_n,
        }

    def remove_duplicates_all(
        self,
        strategies: Optional[List[str]] = None,
        *,
        dry_run: bool = False,
        merge_fields: bool = True,
    ) -> Dict[str, Any]:
        strats = strategies or ["source_url", "name_dob"]
        results = []
        total_deleted = 0
        total_merged = 0
        for s in strats:
            try:
                r = self.remove_duplicates(
                    s, dry_run=dry_run, merge_fields=merge_fields
                )
            except ValueError:
                continue
            results.append(r)
            total_deleted += int(r.get("deleted") or 0)
            total_merged += int(r.get("merged_fields") or 0)
        return {
            "dry_run": dry_run,
            "strategies": results,
            "total_deleted": total_deleted,
            "total_merged_fields": total_merged,
            "total_offenders": self.get_total_count(),
        }

