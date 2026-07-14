"""Find and summarize name+DOB+photo duplicate groups."""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple


class DedupeIdentityFindMixin:
    """Iterate candidates and find name+DOB+photo clusters."""

    def _iter_name_dob_photo_candidates(
        self,
        *,
        source_system: Optional[str] = None,
        source_systems: Optional[List[str]] = None,
    ):
        where = "WHERE 1=1"
        params: List[Any] = []
        if source_systems:
            systems = [str(s).strip().lower() for s in source_systems if str(s).strip()]
            if systems:
                ph = ",".join("?" for _ in systems)
                where += f" AND LOWER(COALESCE(source_system, '')) IN ({ph})"
                params.extend(systems)
        elif source_system:
            where += " AND LOWER(COALESCE(source_system, '')) = LOWER(?)"
            params.append(source_system)
        sql = f"SELECT * FROM arrests {where} ORDER BY id ASC"
        for row in self._conn.execute(sql, params):
            rec = dict(row)
            name_key = self.normalize_arrest_name(rec)
            dob_key = self.dob_match_key(rec)
            if not name_key or not dob_key:
                continue
            yield name_key, dob_key, rec

    def find_name_dob_photo_duplicate_groups(
        self,
        *,
        source_system: Optional[str] = None,
        source_systems: Optional[List[str]] = None,
        limit_groups: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Find duplicate arrest clusters by normalized name + DOB + photo identity.

        When *source_system* / *source_systems* are omitted, clusters span **all**
        hosts (cross-source dedupe). See ``remove_name_dob_photo_duplicates``.
        """
        buckets: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
        for name_key, dob_key, rec in self._iter_name_dob_photo_candidates(
            source_system=source_system,
            source_systems=source_systems,
        ):
            buckets[(name_key, dob_key)].append(rec)

        groups: List[Dict[str, Any]] = []
        for (name_key, dob_key), members in sorted(
            buckets.items(), key=lambda kv: (-len(kv[1]), kv[0])
        ):
            if len(members) < 2:
                continue
            for dup_set in self._name_dob_photo_duplicate_sets(members):
                if len(dup_set) < 2:
                    continue
                keep = self.pick_name_dob_photo_keeper(dup_set)
                keep_id = int(keep["id"])
                remove_ids = [
                    int(m["id"])
                    for m in dup_set
                    if m.get("id") is not None and int(m["id"]) != keep_id
                ]
                if not remove_ids:
                    continue
                groups.append({
                    "strategy": "name_dob_photo",
                    "key": f"{name_key}|{dob_key}",
                    "name_key": name_key,
                    "dob_key": dob_key,
                    "count": len(dup_set),
                    "ids": [int(m["id"]) for m in dup_set if m.get("id") is not None],
                    "keep_id": keep_id,
                    "remove_ids": remove_ids,
                    "members": dup_set,
                })
                if limit_groups is not None and len(groups) >= int(limit_groups):
                    return groups
        return groups

    def count_name_dob_photo_duplicate_summary(
        self, *, source_system: Optional[str] = None
    ) -> Dict[str, Any]:
        """Report (name, dob) buckets and photo/no-photo breakdown."""
        from scraper.mugshot_ethnicity.photo_quality import record_has_real_photo

        buckets: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
        for name_key, dob_key, rec in self._iter_name_dob_photo_candidates(
            source_system=source_system
        ):
            buckets[(name_key, dob_key)].append(rec)

        multi = 0
        with_photo = 0
        without_photo = 0
        duplicate_groups = 0
        extra_rows = 0
        for members in buckets.values():
            if len(members) < 2:
                continue
            multi += 1
            has = sum(1 for m in members if record_has_real_photo(m))
            lacks = len(members) - has
            if has:
                with_photo += 1
            if lacks:
                without_photo += 1
            for dup_set in self._name_dob_photo_duplicate_sets(members):
                if len(dup_set) < 2:
                    continue
                duplicate_groups += 1
                extra_rows += len(dup_set) - 1

        return {
            "name_dob_buckets": len(buckets),
            "multi_member_buckets": multi,
            "buckets_with_photo": with_photo,
            "buckets_missing_photo": without_photo,
            "duplicate_groups": duplicate_groups,
            "extra_rows": extra_rows,
        }
