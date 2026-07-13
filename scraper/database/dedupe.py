"""Dedupe / merge helpers for arrest rows."""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from scraper.database.constants import _ARREST_COLUMNS, _MERGE_SEP, _MERGE_UNION_FIELDS

# Punctuation stripped when normalizing person names for duplicate keys.
_NAME_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_DOB_SEP_RE = re.compile(r"[/\-.]")


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

    # ---- Name + DOB + photo duplicates (RecentlyBooked misclassify) ----

    @classmethod
    def normalize_arrest_name(cls, record: Dict[str, Any]) -> str:
        """Normalized full name: casefold, trim, collapse space, drop punctuation."""
        full = str(record.get("full_name") or "").strip()
        if not full:
            parts = [
                str(record.get("first_name") or "").strip(),
                str(record.get("middle_name") or "").strip(),
                str(record.get("last_name") or "").strip(),
            ]
            full = " ".join(p for p in parts if p)
        full = _NAME_PUNCT_RE.sub(" ", full)
        return " ".join(full.casefold().split())

    @staticmethod
    def normalize_date_of_birth(dob: Any) -> str:
        """Best-effort DOB key (YYYY-MM-DD when parseable, else compact digits)."""
        raw = str(dob or "").strip()
        if not raw:
            return ""
        compact = _DOB_SEP_RE.sub("/", raw)
        m = re.match(
            r"^(\d{1,2})/(\d{1,2})/(\d{4})$",
            compact,
        )
        if m:
            mm, dd, yyyy = m.group(1), m.group(2), m.group(3)
            return f"{yyyy}-{int(mm):02d}-{int(dd):02d}"
        m = re.match(r"^(\d{4})[/-](\d{1,2})[/-](\d{1,2})$", compact)
        if m:
            yyyy, mm, dd = m.group(1), m.group(2), m.group(3)
            return f"{yyyy}-{int(mm):02d}-{int(dd):02d}"
        digits = re.sub(r"\D", "", raw)
        if len(digits) == 8:
            # YYYYMMDD or MMDDYYYY — prefer month-first when first token > 12
            if int(digits[:4]) > 1900:
                return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
            mm, dd, yyyy = digits[:2], digits[2:4], digits[4:8]
            if int(mm) > 12 and int(dd) <= 12:
                mm, dd = dd, mm
            return f"{yyyy}-{int(mm):02d}-{int(dd):02d}"
        return " ".join(raw.casefold().split())

    @classmethod
    def dob_match_key(cls, record: Dict[str, Any]) -> str:
        """DOB bucket key: normalized date_of_birth, else ``age:N`` when DOB is blank."""
        dob = cls.normalize_date_of_birth(record.get("date_of_birth"))
        if dob:
            return dob
        age = record.get("age")
        if age is not None and str(age).strip() != "":
            try:
                return f"age:{int(age)}"
            except (TypeError, ValueError):
                pass
        return ""

    @staticmethod
    def _photo_url_identity_token(url: str) -> str:
        """Stable token from a mugshot URL (RecentlyBooked image basename, etc.)."""
        raw = str(url or "").strip().casefold()
        if not raw:
            return ""
        # recentlybooked.com/images/2838/PM42MW07082026.jpg → pm42mw07082026
        if "recentlybooked.com/images/" in raw:
            base = raw.rsplit("/", 1)[-1]
            base = re.sub(r"\.(jpe?g|webp|png|gif)$", "", base, flags=re.I)
            return base
        return raw

    @classmethod
    def photo_identity_key(cls, record: Dict[str, Any]) -> Tuple[str, str]:
        """
        Photo identity for duplicate matching.

        Returns (kind, value): ``md5`` hex digest, ``url`` (normalized), or
        ``none`` when no comparable photo identity exists.
        """
        from scraper.mugshot_ethnicity.photo_quality import (
            file_md5,
            is_placeholder_photo_url,
            record_has_real_photo,
        )

        if not record_has_real_photo(record):
            return ("none", "")

        path = str(record.get("photo_path") or "").strip()
        if path:
            p = Path(path)
            if p.is_file():
                digest = file_md5(p)
                if digest:
                    return ("md5", digest)

        url = str(record.get("photo_url") or "").strip()
        url_cf = url.casefold()
        if url_cf and not is_placeholder_photo_url(url):
            token = cls._photo_url_identity_token(url)
            if token:
                return ("url", token)

        return ("none", "")

    @classmethod
    def _same_photo_identity(
        cls, a: Dict[str, Any], b: Dict[str, Any]
    ) -> bool:
        ka = cls.photo_identity_key(a)
        kb = cls.photo_identity_key(b)
        if ka[0] == "none" or kb[0] == "none":
            return False
        return ka == kb

    @classmethod
    def _name_dob_photo_duplicate_sets(
        cls, members: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """
        Within a (normalized name, DOB) bucket, return duplicate member lists.

        Match rule: same normalized name + DOB + photo identity (byte-identical
        file MD5 or shared photo_url). When exactly one distinct real photo
        exists in the bucket, rows without a real photo are duplicates of it.
        """
        from scraper.mugshot_ethnicity.photo_quality import record_has_real_photo

        if len(members) < 2:
            return []

        photo_holders = [m for m in members if record_has_real_photo(m)]
        no_photo = [m for m in members if not record_has_real_photo(m)]

        photo_clusters: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
        for m in photo_holders:
            photo_clusters[cls.photo_identity_key(m)].append(m)

        sets: List[List[Dict[str, Any]]] = []
        if not photo_clusters:
            if len(members) > 1:
                sets.append(list(members))
            return sets

        if len(photo_clusters) == 1:
            cluster = list(next(iter(photo_clusters.values()))) + no_photo
            if len(cluster) > 1:
                sets.append(cluster)
            return sets

        for key, cluster in photo_clusters.items():
            if key[0] != "none" and len(cluster) > 1:
                sets.append(list(cluster))
        return sets

    @classmethod
    def _keeper_priority_score(cls, row: Dict[str, Any]) -> Tuple[int, int, int]:
        """Higher is better; final tie-break uses negative id (lower id wins)."""
        from scraper.searcher import ethnicity_review_verdict

        score = 0
        if ethnicity_review_verdict(row):
            score += 100
        if str(row.get("likely_ethnicity") or "").strip():
            score += 50
        from scraper.mugshot_ethnicity.photo_quality import record_has_real_photo

        if record_has_real_photo(row):
            score += 200
        score += cls._row_richness(row)
        rid = int(row.get("id") or 0)
        return (score, -rid, rid)

    @classmethod
    def pick_name_dob_photo_keeper(
        cls, members: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Choose survivor: prefer real photo, then ethnicity review / likely_ethnicity,
        then completeness, then lowest id.
        """
        return max(members, key=cls._keeper_priority_score)

    def _iter_name_dob_photo_candidates(
        self, *, source_system: Optional[str] = None
    ):
        where = "WHERE 1=1"
        params: List[Any] = []
        if source_system:
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
        limit_groups: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Find duplicate arrest clusters by normalized name + DOB + photo identity.

        See ``remove_name_dob_photo_duplicates`` for the resolution rule.
        """
        buckets: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
        for name_key, dob_key, rec in self._iter_name_dob_photo_candidates(
            source_system=source_system
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

    def _delete_orphan_photo_files(self, photo_paths: List[str]) -> int:
        """Remove photo files no longer referenced by any arrests row."""
        from scraper.mugshot_ethnicity.photo_quality import is_placeholder_photo

        removed = 0
        for raw in photo_paths:
            path = str(raw or "").strip()
            if not path:
                continue
            p = Path(path)
            if not p.is_file():
                continue
            row = self._conn.execute(
                "SELECT COUNT(*) FROM arrests WHERE photo_path = ?",
                (path,),
            ).fetchone()
            refs = int(row[0]) if row else 0
            if refs > 0:
                continue
            if is_placeholder_photo(p):
                try:
                    p.unlink()
                    removed += 1
                except OSError:
                    pass
                continue
            try:
                p.unlink()
                removed += 1
            except OSError:
                pass
        return removed

    def remove_name_dob_photo_duplicates(
        self,
        *,
        dry_run: bool = False,
        merge_fields: bool = True,
        source_system: Optional[str] = None,
        delete_orphan_photos: bool = True,
    ) -> Dict[str, Any]:
        """
        Delete duplicate arrests matched on normalized name + DOB + photo.

        Resolution: keep the row with a real mugshot over rows without one;
        otherwise keep the row with an ethnicity review / likely_ethnicity,
        then the richest row, then the lowest id. Merges non-empty fields from
        losers into the keeper before deletion. Orphan photo files are removed
        only when no remaining row references ``photo_path``.
        """
        groups = self.find_name_dob_photo_duplicate_groups(
            source_system=source_system
        )
        deleted_ids: List[int] = []
        merged_n = 0
        orphan_paths: List[str] = []
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
            for loser in losers:
                path = str(loser.get("photo_path") or "").strip()
                if path:
                    orphan_paths.append(path)
            if merge_fields and losers:
                updates = self.merge_duplicate_members(keep_row, losers)
                if updates and not dry_run:
                    self.update_arrest(keep_id, updates)
                    keep_row.update(updates)
                    merged_n += len(updates)
                elif updates:
                    merged_n += len(updates)
            if not dry_run and remove_ids:
                ph = ",".join("?" for _ in remove_ids)
                self._conn.execute(
                    f"DELETE FROM arrests WHERE id IN ({ph})", remove_ids
                )
            deleted_ids.extend(remove_ids)

        photos_removed = 0
        if not dry_run:
            if deleted_ids:
                self._conn.commit()
            if delete_orphan_photos and orphan_paths:
                photos_removed = self._delete_orphan_photo_files(orphan_paths)

        return {
            "strategy": "name_dob_photo",
            "dry_run": dry_run,
            "groups": kept,
            "deleted": len(deleted_ids),
            "deleted_ids": deleted_ids,
            "merged_fields": merged_n,
            "orphan_photos_removed": photos_removed,
            "total_offenders": self.get_total_count() if not dry_run else None,
        }

