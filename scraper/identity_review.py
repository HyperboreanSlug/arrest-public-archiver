"""Person-level identity helpers for ethnicity confirmation queues.

Confirmation is stored per arrest row in ``flags``, but the same person can
appear as multiple bookings. These helpers:

  * find strong identity siblings so a verdict can be propagated
  * track which identity keys are already confirmed
  * dedupe classification queues so one person is shown once
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from scraper.mugshot_sources.identity import identity_keys_for_record
from scraper.searcher_names import ethnicity_review_verdict

# Strongest first — used for sibling matching and queue keys.
_STRONG_PREFIXES = (
    "name_dob:",
    "name_dob_st:",
    "photo:",
    "booking:",
    "name_bdate:",
)

_SIBLING_COLS = (
    "id, first_name, middle_name, last_name, full_name, date_of_birth, age, "
    "state, booking_date, arrest_date, booking_id, source_url, photo_url, "
    "photo_path, source_system, flags, likely_ethnicity"
)


def strong_identity_keys(record: Dict[str, Any]) -> List[str]:
    """Identity keys strong enough to treat rows as the same person."""
    keys = identity_keys_for_record(record)
    strong = [
        k
        for k in keys
        if any(k.startswith(p) for p in _STRONG_PREFIXES)
    ]
    return strong or list(keys)


def person_queue_key(record: Dict[str, Any]) -> str:
    """Stable key for one person in a classification queue."""
    keys = strong_identity_keys(record)
    if keys:
        # Prefer name+DOB, then photo, then anything else.
        for prefix in _STRONG_PREFIXES:
            for k in keys:
                if k.startswith(prefix):
                    return k
        return keys[0]
    rid = record.get("id")
    if rid is not None:
        return f"id:{int(rid)}"
    url = str(record.get("source_url") or "").strip()
    return f"url:{url}" if url else "unknown"


def shares_identity(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """True when *a* and *b* share a strong identity key."""
    ka = set(strong_identity_keys(a))
    if not ka:
        return False
    return bool(ka & set(strong_identity_keys(b)))


def load_reviewed_identity_keys(db: Any) -> Set[str]:
    """All strong identity keys that already have a confirmation verdict."""
    out: Set[str] = set()
    try:
        rows = db._conn.execute(
            f"SELECT {_SIBLING_COLS} FROM arrests "
            "WHERE flags IS NOT NULL AND TRIM(flags) != '' "
            "AND flags LIKE '%ethnicity_review%'"
        ).fetchall()
    except Exception:
        return out
    for row in rows:
        rec = dict(row)
        if not ethnicity_review_verdict(rec):
            continue
        out.update(strong_identity_keys(rec))
    return out


def is_person_reviewed(
    record: Dict[str, Any],
    reviewed_keys: Optional[Set[str]] = None,
) -> bool:
    """True if this row or any linked identity key is already confirmed."""
    if ethnicity_review_verdict(record):
        return True
    if not reviewed_keys:
        return False
    return bool(set(strong_identity_keys(record)) & reviewed_keys)


def find_identity_siblings(db: Any, record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Load DB rows that share a strong identity key with *record* (incl. self)."""
    keys = set(strong_identity_keys(record))
    rid = record.get("id")
    if not keys:
        if rid is None:
            return []
        row = db._conn.execute(
            f"SELECT {_SIBLING_COLS} FROM arrests WHERE id = ?",
            (int(rid),),
        ).fetchone()
        return [dict(row)] if row else []

    last = str(record.get("last_name") or "").strip()
    full = str(record.get("full_name") or "").strip()
    params: List[Any] = []
    clauses: List[str] = []
    if last:
        clauses.append("last_name = ? COLLATE NOCASE")
        params.append(last)
    if full:
        clauses.append("full_name = ? COLLATE NOCASE")
        params.append(full)
    if rid is not None:
        clauses.append("id = ?")
        params.append(int(rid))
    # Photo basename fallback when name is empty/odd.
    path = str(record.get("photo_path") or "").strip()
    if path:
        clauses.append("photo_path = ?")
        params.append(path)

    if clauses:
        sql = f"SELECT {_SIBLING_COLS} FROM arrests WHERE " + " OR ".join(clauses)
        candidates = [dict(r) for r in db._conn.execute(sql, params).fetchall()]
    else:
        candidates = [
            dict(r)
            for r in db._conn.execute(f"SELECT {_SIBLING_COLS} FROM arrests").fetchall()
        ]

    out: List[Dict[str, Any]] = []
    seen: Set[int] = set()
    for rec in candidates:
        i = rec.get("id")
        if i is not None and int(i) in seen:
            continue
        if set(strong_identity_keys(rec)) & keys:
            if i is not None:
                seen.add(int(i))
            out.append(rec)
    if rid is not None and int(rid) not in seen:
        # Always include self even if keys failed to match candidates.
        row = db._conn.execute(
            f"SELECT {_SIBLING_COLS} FROM arrests WHERE id = ?",
            (int(rid),),
        ).fetchone()
        if row:
            out.append(dict(row))
    return out


def dedupe_records_by_person(
    records: Sequence[Dict[str, Any]],
    *,
    prefer_confidence: bool = True,
) -> List[Dict[str, Any]]:
    """Keep one row per person for classification queues."""
    best: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for rec in records:
        key = person_queue_key(rec)
        if key not in best:
            best[key] = rec
            order.append(key)
            continue
        if not prefer_confidence:
            continue
        prev = best[key]
        prev_c = float(prev.get("name_confidence") or prev.get("confidence") or 0)
        cur_c = float(rec.get("name_confidence") or rec.get("confidence") or 0)
        # Prefer higher confidence; then prefer row that already has an id.
        if cur_c > prev_c or (
            cur_c == prev_c and rec.get("id") is not None and prev.get("id") is None
        ):
            best[key] = rec
    return [best[k] for k in order]


def filter_unreviewed_people(
    records: Iterable[Dict[str, Any]],
    reviewed_keys: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    """Drop confirmed rows and siblings of confirmed people; then person-dedupe."""
    kept: List[Dict[str, Any]] = []
    for rec in records:
        if is_person_reviewed(rec, reviewed_keys):
            continue
        kept.append(rec)
    return dedupe_records_by_person(kept)
