"""Field-based find/remove_duplicates (source_url, name_dob)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from scraper.database.dedupe_merge_fields import DedupeMergeFieldsMixin


class DedupeMergeMixin(DedupeMergeFieldsMixin):
    """Find and remove duplicates by source_url or name+DOB."""

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
            ph = ",".join("?" for _ in ids)
            members = [
                dict(row)
                for row in self._conn.execute(
                    f"SELECT * FROM arrests WHERE id IN ({ph})", ids
                ).fetchall()
            ]
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
            members_by_id = {int(m["id"]): m for m in g["members"]}
            keep_row = members_by_id.get(keep_id)
            if not keep_row or not remove_ids:
                continue
            kept += 1
            losers = [members_by_id[i] for i in remove_ids if i in members_by_id]
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
