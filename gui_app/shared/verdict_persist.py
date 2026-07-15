"""Persist ethnicity classification confirmations to arrests.flags."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from gui_app.shared.record_sidebar_flags import merge_ethnicity_review_flags
from scraper.database import Database
from scraper.identity_review import find_identity_siblings
from scraper.searcher import ethnicity_review_verdict


def persist_ethnicity_verdict(
    db_path: str,
    record: Dict[str, Any],
    verdict: str,
    *,
    extra_fields: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, Optional[str], str]:
    """
    Write ``ethnicity_review`` into flags and verify the round-trip.

    Propagates the same confirmation to strong identity siblings so the same
    person is not offered for classification again under another booking.

    Returns ``(ok, flags_json, error_message)``. On success, *record* is
    updated in-place with ``id`` and ``flags``.
    """
    verdict = (verdict or "").strip().lower()
    if verdict not in ("correct", "incorrect"):
        return False, None, f"Invalid verdict: {verdict!r}"

    flags_json = merge_ethnicity_review_flags(record.get("flags"), verdict)
    rid = record.get("id")
    source_url = str(record.get("source_url") or "").strip()
    extras = {k: v for k, v in (extra_fields or {}).items() if v is not None}

    db = Database(db_path)
    try:
        if rid is None and source_url:
            row = db._conn.execute(
                "SELECT id, flags FROM arrests WHERE source_url = ? LIMIT 1",
                (source_url,),
            ).fetchone()
            if row:
                rid = row["id"] if hasattr(row, "keys") else row[0]
                existing = row["flags"] if hasattr(row, "keys") else row[1]
                flags_json = merge_ethnicity_review_flags(existing, verdict)
                record["id"] = rid

        if rid is None:
            return False, flags_json, "Record has no database id — import first."

        rid_i = int(rid)
        record["id"] = rid_i
        # Resolve full row for sibling matching (photo/DOB keys).
        base = db._conn.execute(
            "SELECT * FROM arrests WHERE id = ?", (rid_i,)
        ).fetchone()
        seed = dict(base) if base else dict(record)
        seed.update(record)

        siblings = find_identity_siblings(db, seed)
        if not siblings:
            siblings = [seed]

        updated_ids: List[int] = []
        for sib in siblings:
            sid = sib.get("id")
            if sid is None:
                continue
            sid_i = int(sid)
            # Preserve per-row notes etc.; set same ethnicity_review verdict.
            row_flags = merge_ethnicity_review_flags(sib.get("flags"), verdict)
            patch: Dict[str, Any] = {"flags": row_flags}
            for k, v in extras.items():
                # Only fill empty likely_ethnicity on siblings unless primary.
                if k == "likely_ethnicity" and sid_i != rid_i:
                    if str(sib.get("likely_ethnicity") or "").strip():
                        continue
                patch[k] = v
            if not db.update_arrest(sid_i, patch):
                # Row may already hold identical values — accept if still present.
                exists = db._conn.execute(
                    "SELECT 1 FROM arrests WHERE id = ?", (sid_i,)
                ).fetchone()
                if not exists:
                    return False, flags_json, f"Database update failed for id={sid_i}."
            updated_ids.append(sid_i)

        if rid_i not in updated_ids:
            return False, flags_json, f"Database update failed for id={rid_i}."

        row = db._conn.execute(
            "SELECT flags FROM arrests WHERE id = ?",
            (rid_i,),
        ).fetchone()
        saved = row["flags"] if row and hasattr(row, "keys") else (row[0] if row else None)
        if ethnicity_review_verdict({"flags": saved}) != verdict:
            return (
                False,
                saved if isinstance(saved, str) else flags_json,
                "Save did not stick — flags mismatch after write.",
            )

        # Verify siblings also stuck (best-effort; primary already checked).
        for sid_i in updated_ids:
            if sid_i == rid_i:
                continue
            srow = db._conn.execute(
                "SELECT flags FROM arrests WHERE id = ?", (sid_i,)
            ).fetchone()
            sflags = (
                srow["flags"] if srow and hasattr(srow, "keys") else (srow[0] if srow else None)
            )
            if ethnicity_review_verdict({"flags": sflags}) != verdict:
                return (
                    False,
                    saved if isinstance(saved, str) else flags_json,
                    f"Sibling id={sid_i} confirmation did not stick.",
                )

        record["flags"] = saved if isinstance(saved, str) else flags_json
        record["_confirmed_sibling_ids"] = updated_ids
        return True, record["flags"], ""
    finally:
        db.close()
