"""Backfill charge_description when it is a state name or bare case number.

Sources of truth:
  - mugshots.com: Offense (etc.) in raw_json.fields
  - recentlybooked: reparse saved HTML (Charge Code + Description)
"""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scraper.charge_chrome import has_charge_table_chrome  # noqa: E402
from scraper.charge_classifications import classify_charge  # noqa: E402
from scraper.charge_recover import recover_charge_from_record  # noqa: E402
from scraper.charge_sanitize import (  # noqa: E402
    is_case_number,
    is_non_charge,
    sanitize_charge_text,
)

_SEG = re.compile(r"\s*[;|]\s*")


def _needs_fix(charge: str) -> bool:
    """State names, case numbers, N/A stubs, mugshots table chrome."""
    s = (charge or "").strip()
    if not s:
        return False
    if is_case_number(s) or is_non_charge(s) or has_charge_table_chrome(s):
        return True
    for part in _SEG.split(s):
        p = part.strip()
        if p and (is_non_charge(p) or is_case_number(p) or has_charge_table_chrome(p)):
            return True
    # Sanitizer would change text (chrome strip / junk segments)
    cleaned = sanitize_charge_text(s)
    return bool(cleaned) and cleaned != s


def backfill(db_path: str = "data/arrests.db", dry_run: bool = False) -> int:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT id, charge_description, case_number, source_system, html_path,
               source_url, raw_json
        FROM arrests
        WHERE charge_description IS NOT NULL AND TRIM(charge_description) != ''
        """
    ).fetchall()

    updated = 0
    for r in rows:
        charge = r["charge_description"] or ""
        if not _needs_fix(charge):
            continue
        rec = dict(r)
        new_charge = None
        new_case = r["case_number"]

        if r["source_system"] == "recentlybooked" and r["html_path"]:
            hp = Path(r["html_path"])
            if hp.is_file():
                from scraper.recentlybooked.parse_detail import parse_detail

                parsed = parse_detail(
                    hp.read_text(encoding="utf-8", errors="replace"),
                    r["source_url"] or "",
                )
                new_charge = parsed.get("charge_description")
                if parsed.get("case_number"):
                    new_case = parsed.get("case_number")

        if not new_charge:
            recovered = recover_charge_from_record(rec)
            if recovered:
                new_charge = recovered

        if not new_charge:
            cleaned = sanitize_charge_text(charge)
            new_charge = cleaned if cleaned and not is_non_charge(cleaned) else None

        # Move bare case numbers into case_number when no better charge found
        if is_case_number(charge):
            new_case = new_case or charge.strip()

        if new_charge == charge and new_case == r["case_number"]:
            continue

        cat = classify_charge(
            {
                "charge_description": new_charge or "",
                "raw_json": r["raw_json"],
            }
        )
        if dry_run:
            print(
                f"id={r['id']} {charge!r} -> {new_charge!r} "
                f"case={new_case!r} cat={cat}"
            )
        else:
            conn.execute(
                """
                UPDATE arrests
                SET charge_description = ?, case_number = ?, charge_category = ?
                WHERE id = ?
                """,
                (new_charge, new_case, cat, r["id"]),
            )
        updated += 1

    if not dry_run:
        conn.commit()
    conn.close()
    return updated


def main() -> None:
    dry = "--dry-run" in sys.argv
    db = "data/arrests.db"
    for a in sys.argv[1:]:
        if a.endswith(".db"):
            db = a
    n = backfill(db, dry_run=dry)
    print(f"{'Would update' if dry else 'Updated'} {n} rows")


if __name__ == "__main__":
    main()
