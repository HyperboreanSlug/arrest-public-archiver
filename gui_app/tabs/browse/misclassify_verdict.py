"""Browse classification verification + stated→actual race sync."""
from __future__ import annotations

from typing import Any, Dict

from gui_app.shared.record_sidebar import merge_race_manual_flags
from gui_app.shared.verdict_persist import persist_ethnicity_verdict
from gui_app.tabs.browse.misclassify_constants import actual_from_stated_race


def apply_browse_verdict(
    *,
    db_path: str,
    db: Any,
    record: Dict[str, Any],
    verdict: str,
) -> tuple[bool, str, Dict[str, Any]]:
    """
    Persist verification. When *correct*, set actual race from stated race.

    Returns ``(ok, error_or_empty, updated_record)``. Confirmation is written to
    identity siblings so the same person is not re-queued under another booking.
    """
    extras: Dict[str, Any] = {}
    if verdict == "correct":
        actual = actual_from_stated_race(record.get("race"))
        if actual:
            extras["likely_ethnicity"] = actual

    try:
        ok, flags_json, err = persist_ethnicity_verdict(
            db_path, record, verdict, extra_fields=extras or None
        )
    except Exception as exc:
        return False, str(exc), record
    if not ok:
        return False, err or "unknown error", record
    if flags_json:
        record["flags"] = flags_json

    if verdict == "correct" and extras.get("likely_ethnicity"):
        actual = extras["likely_ethnicity"]
        record["likely_ethnicity"] = actual
        flags_json = merge_race_manual_flags(record.get("flags"))
        record["flags"] = flags_json
        ids = list(record.get("_confirmed_sibling_ids") or [])
        rid = record.get("id")
        if rid is not None and int(rid) not in {int(x) for x in ids}:
            ids.append(int(rid))
        target = db
        close = False
        try:
            if target is None:
                from scraper.database import Database

                target = Database(db_path)
                close = True
            for sid in ids:
                try:
                    # Re-merge race_manual onto each sibling's post-verdict flags.
                    row = target._conn.execute(
                        "SELECT flags FROM arrests WHERE id = ?", (int(sid),)
                    ).fetchone()
                    raw = row["flags"] if row else flags_json
                    target.update_arrest(
                        int(sid),
                        {
                            "likely_ethnicity": actual,
                            "flags": merge_race_manual_flags(raw),
                        },
                    )
                except Exception:
                    pass
            # Refresh primary flags from DB.
            if rid is not None:
                row = target._conn.execute(
                    "SELECT flags FROM arrests WHERE id = ?", (int(rid),)
                ).fetchone()
                if row and row["flags"]:
                    record["flags"] = row["flags"]
        except Exception as exc:
            return True, f"actual race not saved: {exc}", record
        finally:
            if close and target is not None:
                try:
                    target.close()
                except Exception:
                    pass
    return True, "", record
