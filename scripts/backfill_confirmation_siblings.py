"""Propagate existing ethnicity_review flags to identity siblings.

Fixes rows that were confirmed before sibling propagation existed, so the
same person does not reappear under another booking as Unverified.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gui_app.shared.record_sidebar_flags import merge_ethnicity_review_flags  # noqa: E402
from scraper.database import get_database  # noqa: E402
from scraper.identity_review import find_identity_siblings  # noqa: E402
from scraper.searcher import ethnicity_review_verdict  # noqa: E402


def backfill(*, dry_run: bool = False) -> dict:
    db = get_database()
    confirmed = [
        dict(r)
        for r in db._conn.execute(
            "SELECT * FROM arrests "
            "WHERE flags IS NOT NULL AND flags LIKE '%ethnicity_review%'"
        ).fetchall()
        if ethnicity_review_verdict(dict(r))
    ]
    updated = 0
    groups = 0
    for rec in confirmed:
        verdict = ethnicity_review_verdict(rec)
        if not verdict:
            continue
        siblings = find_identity_siblings(db, rec)
        touched = False
        for sib in siblings:
            if ethnicity_review_verdict(sib) == verdict:
                continue
            sid = sib.get("id")
            if sid is None:
                continue
            flags = merge_ethnicity_review_flags(sib.get("flags"), verdict)
            if dry_run:
                print(
                    f"would update id={sid} name={sib.get('full_name')!r} "
                    f"→ {verdict} (from id={rec.get('id')})"
                )
            else:
                db.update_arrest(int(sid), {"flags": flags})
            updated += 1
            touched = True
        if touched:
            groups += 1
    return {"confirmed_seeds": len(confirmed), "updated": updated, "groups": groups}


def main() -> None:
    dry = "--dry-run" in sys.argv
    stats = backfill(dry_run=dry)
    print(
        f"{'Would update' if dry else 'Updated'} {stats['updated']} sibling row(s) "
        f"across {stats['groups']} group(s) "
        f"(from {stats['confirmed_seeds']} confirmed seeds)"
    )


if __name__ == "__main__":
    main()
