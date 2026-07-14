"""Remove name+DOB+photo duplicates and orphan photo files."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from scraper.database.dedupe_identity_find import DedupeIdentityFindMixin


class DedupeIdentityOpsMixin(DedupeIdentityFindMixin):
    """Delete duplicate clusters and clean orphan mugshot files."""

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
        source_systems: Optional[List[str]] = None,
        delete_orphan_photos: bool = True,
    ) -> Dict[str, Any]:
        """
        Delete duplicate arrests matched on normalized name + DOB + photo.

        Resolution: keep the row with a real mugshot over rows without one;
        otherwise keep the row with an ethnicity review / likely_ethnicity,
        then the richest row, then the lowest id. Merges non-empty fields from
        losers into the keeper before deletion (including multi-host
        ``source_system`` / ``source_url`` unions). Orphan photo files are
        removed only when no remaining row references ``photo_path``.

        Omit *source_system* to dedupe **across** mugshot hosts.
        """
        groups = self.find_name_dob_photo_duplicate_groups(
            source_system=source_system,
            source_systems=source_systems,
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
            "cross_source": source_system is None and not source_systems,
        }
