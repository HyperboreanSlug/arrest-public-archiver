"""Booking/arrest date window helpers (last N days / weeks)."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, List, Optional, Tuple


def cutoff_iso(
    *,
    days: Optional[int] = None,
    weeks: Optional[int] = None,
    today: Optional[date] = None,
) -> Optional[str]:
    """Return YYYY-MM-DD cutoff for ``date >= cutoff``, or None if no window."""
    base = today or date.today()
    if weeks is not None:
        n = int(weeks)
        if n > 0:
            return (base - timedelta(weeks=n)).isoformat()
        return None
    if days is not None:
        n = int(days)
        if n > 0:
            return (base - timedelta(days=n)).isoformat()
        return None
    return None


def resolve_cutoff(
    amount: Any,
    unit: Any,
    *,
    today: Optional[date] = None,
) -> Optional[str]:
    """Parse UI amount + unit (``days`` / ``weeks``) into an ISO cutoff date."""
    if amount is None:
        return None
    raw = str(amount).strip().lower()
    if not raw or raw in ("all", "any", "0", "*"):
        return None
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return None
    if n <= 0:
        return None
    u = str(unit or "days").strip().lower()
    if u.startswith("week"):
        return cutoff_iso(weeks=n, today=today)
    return cutoff_iso(days=n, today=today)


# ISO prefix of arrest_date / booking_date (handles ``YYYY-MM-DD`` and ``…T…``).
_EVENT_DATE_SQL = (
    "substr(replace(COALESCE("
    "NULLIF(TRIM(arrest_date), ''), "
    "NULLIF(TRIM(booking_date), '')"
    "), 'T', ' '), 1, 10)"
)


def sql_since_date(cutoff: str) -> Tuple[str, List[Any]]:
    """SQL fragment + params: event date is ISO and on/after cutoff."""
    cut = str(cutoff or "").strip()[:10]
    if len(cut) != 10:
        return "", []
    expr = _EVENT_DATE_SQL
    clause = (
        f" AND {expr} GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'"
        f" AND {expr} >= ?"
    )
    return clause, [cut]
