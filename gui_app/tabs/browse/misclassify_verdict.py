"""Browse classification verification + stated→actual race sync."""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

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

    Returns ``(ok, error_or_empty, updated_record)``.
    """
    try:
        ok, flags_json, err = persist_ethnicity_verdict(db_path, record, verdict)
    except Exception as exc:
        return False, str(exc), record
    if not ok:
        return False, err or "unknown error", record
    if flags_json:
        record["flags"] = flags_json

    if verdict == "correct":
        actual = actual_from_stated_race(record.get("race"))
        if actual:
            flags_json = merge_race_manual_flags(record.get("flags"))
            record["flags"] = flags_json
            record["likely_ethnicity"] = actual
            rid = record.get("id")
            if rid is not None and db is not None:
                try:
                    db.update_arrest(
                        int(rid),
                        {"likely_ethnicity": actual, "flags": flags_json},
                    )
                except Exception as exc:
                    return True, f"actual race not saved: {exc}", record
    return True, "", record
