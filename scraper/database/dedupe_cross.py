"""Cross-source dedupe and import-time identity keys."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set


class DedupeCrossMixin:
    """Cross-host duplicate removal and identity key inventory."""

    def remove_cross_source_duplicates(
        self,
        *,
        dry_run: bool = False,
        merge_fields: bool = True,
        source_systems: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Robust cross-host dedupe for mugshot aggregators.

        Matches the same person (name + DOB + photo identity) even when rows
        come from RecentlyBooked, Mugshots.com, Busted Newspaper, etc.
        """
        return self.remove_name_dob_photo_duplicates(
            dry_run=dry_run,
            merge_fields=merge_fields,
            source_system=None,
            source_systems=source_systems,
            delete_orphan_photos=True,
        )

    def existing_identity_keys(self) -> Set[str]:
        """All identity keys currently in the DB (for import-time skip)."""
        from scraper.mugshot_sources import identity_keys_for_record

        keys: Set[str] = set()
        try:
            rows = self._conn.execute(
                "SELECT first_name, middle_name, last_name, full_name, "
                "date_of_birth, age, state, booking_date, arrest_date, "
                "booking_id, source_url, photo_url, photo_path, source_system "
                "FROM arrests"
            ).fetchall()
        except Exception:
            return keys
        for row in rows:
            for k in identity_keys_for_record(dict(row)):
                keys.add(k)
        return keys
