"""Backfill NC DAC mugshots from public OPI into existing arrest rows."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from scraper.nc_dac.opi_photo import OpiPhotoClient, photo_dest
from scraper.nc_dac.opi_urls import detail_url, normalize_doc, picture_url

SOURCE_SYSTEM = "nc_dac"
DEFAULT_PHOTO_ROOT = Path("data/photos/nc_dac")


def _log(msg: str) -> None:
    print(msg, flush=True)


def select_candidates(
    db: Any,
    *,
    limit: int = 0,
    force: bool = False,
    active_only: bool = False,
    inmates_only: bool = False,
    missing_only: bool = True,
) -> List[Dict[str, Any]]:
    """Pick nc_dac rows that need (or may re-fetch) OPI photos."""
    where = ["source_system = ?", "booking_id IS NOT NULL", "TRIM(booking_id) != ''"]
    params: List[Any] = [SOURCE_SYSTEM]
    if missing_only and not force:
        where.append(
            "(photo_path IS NULL OR TRIM(photo_path) = '' "
            "OR photo_url IS NULL OR TRIM(photo_url) = '')"
        )
    if inmates_only:
        # Inmate bulk ids are nc_dac:{doc}; P&P uses nc_dac_pp:{doc}
        where.append("(source_id IS NULL OR source_id NOT LIKE 'nc_dac_pp:%')")
    if active_only:
        # Avoid bare %ACTIVE% — that matches INACTIVE too.
        where.append(
            "("
            "upper(coalesce(agency,'')) LIKE '% CI%' "
            "OR upper(coalesce(agency,'')) LIKE '% CORR%' "
            "OR upper(coalesce(agency,'')) LIKE '% PRISON%' "
            "OR upper(coalesce(raw_json,'')) LIKE '%\"ADMIN_STATUS\":\"ACTIVE\"%' "
            "OR upper(coalesce(raw_json,'')) LIKE '%\"RECORD_STATUS\":\"ACTIVE\"%' "
            ")"
        )
        where.append(
            "upper(coalesce(raw_json,'')) NOT LIKE '%\"ADMIN_STATUS\":\"INACTIVE\"%'"
        )
    # Prefer facility inmates / explicit ACTIVE, higher DOC (often more recent)
    order = (
        "CASE "
        "WHEN upper(coalesce(agency,'')) LIKE '% CI%' THEN 0 "
        "WHEN upper(coalesce(agency,'')) LIKE '% CORR%' THEN 1 "
        "WHEN upper(coalesce(raw_json,'')) LIKE '%\"ADMIN_STATUS\":\"ACTIVE\"%' THEN 2 "
        "ELSE 3 END, "
        "CAST(booking_id AS INTEGER) DESC"
    )
    sql = (
        "SELECT id, booking_id, source_id, full_name, agency, photo_path, photo_url "
        f"FROM arrests WHERE {' AND '.join(where)} "
        f"ORDER BY {order}"
    )
    if limit and limit > 0:
        sql += f" LIMIT {int(limit)}"
    cur = db._conn.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def _apply_photo(
    db: Any,
    *,
    doc: str,
    path: Path,
    update_all_doc: bool = True,
    row_id: Optional[int] = None,
) -> int:
    """Write photo_path/url (+ detail source_url) for one or all rows with DOC."""
    fields = {
        "photo_path": str(path).replace("\\", "/"),
        "photo_url": picture_url(doc),
        "source_url": detail_url(doc),
    }
    n = 0
    if update_all_doc:
        cur = db._conn.execute(
            "SELECT id FROM arrests WHERE source_system = ? AND booking_id = ?",
            (SOURCE_SYSTEM, doc),
        )
        ids = [int(r[0]) for r in cur.fetchall()]
        # also match unpadded / zero-padded variants
        alt = normalize_doc(doc)
        if alt and alt != doc:
            cur = db._conn.execute(
                "SELECT id FROM arrests WHERE source_system = ? AND booking_id = ?",
                (SOURCE_SYSTEM, alt),
            )
            ids.extend(int(r[0]) for r in cur.fetchall())
        seen = set()
        for rid in ids:
            if rid in seen:
                continue
            seen.add(rid)
            if db.update_arrest(rid, fields):
                n += 1
        return n
    if row_id is not None and db.update_arrest(int(row_id), fields):
        return 1
    return 0


def enrich_nc_dac_photos(
    *,
    database: Path | str = "data/arrests.db",
    output_root: Path | str = DEFAULT_PHOTO_ROOT,
    limit: int = 0,
    delay: float = 0.75,
    force: bool = False,
    active_only: bool = False,
    inmates_only: bool = False,
    missing_only: bool = True,
    update_all_doc: bool = True,
) -> Dict[str, int]:
    """
    For each candidate nc_dac row, fetch OPI mugshot and attach to the DB.

    Skips the public “No Photo Available” tile. Polite delay between requests.
    """
    from scraper.database import Database

    db = Database(str(database))
    client = OpiPhotoClient(delay=delay)
    totals = {
        "candidates": 0,
        "fetched": 0,
        "cached": 0,
        "no_photo": 0,
        "errors": 0,
        "updated_rows": 0,
        "docs_done": 0,
    }
    seen_docs: set[str] = set()
    try:
        rows = select_candidates(
            db,
            limit=limit,
            force=force,
            active_only=active_only,
            inmates_only=inmates_only,
            missing_only=missing_only,
        )
        totals["candidates"] = len(rows)
        _log(
            f"NC DAC photo enrich: {len(rows):,} candidates "
            f"(active_only={active_only} inmates_only={inmates_only} force={force})"
        )
        for i, rec in enumerate(rows, 1):
            doc = normalize_doc(str(rec.get("booking_id") or ""))
            if not doc:
                totals["errors"] += 1
                continue
            if doc in seen_docs:
                continue
            seen_docs.add(doc)

            # Reuse on-disk file when present
            dest = photo_dest(doc, output_root)
            if dest.is_file() and not force:
                from scraper.mugshot_ethnicity.photo_quality import is_placeholder_photo

                if not is_placeholder_photo(dest):
                    n = _apply_photo(
                        db,
                        doc=doc,
                        path=dest,
                        update_all_doc=update_all_doc,
                        row_id=rec.get("id"),
                    )
                    totals["cached"] += 1
                    totals["updated_rows"] += n
                    totals["docs_done"] += 1
                    continue

            path, reason = client.download(
                doc, output_root=output_root, force=force
            )
            if path is None:
                if reason in ("no_photo", "placeholder", "too_small"):
                    totals["no_photo"] += 1
                else:
                    totals["errors"] += 1
                if i % 50 == 0 or i == 1:
                    _log(
                        f"  … {i}/{len(rows)} doc={doc} skip={reason} "
                        f"ok={totals['docs_done']} no_photo={totals['no_photo']}"
                    )
                continue

            n = _apply_photo(
                db,
                doc=doc,
                path=path,
                update_all_doc=update_all_doc,
                row_id=rec.get("id"),
            )
            totals["fetched"] += 1 if reason == "ok" else 0
            if reason == "cached":
                totals["cached"] += 1
            totals["updated_rows"] += n
            totals["docs_done"] += 1
            if i % 25 == 0 or totals["docs_done"] <= 3:
                name = (rec.get("full_name") or "")[:28]
                _log(
                    f"  + photo doc={doc} {name} "
                    f"rows={n} ({totals['docs_done']} docs, "
                    f"{totals['updated_rows']} row updates)"
                )
    finally:
        client.close()
        db.close()
    _log(
        f"Done: docs_done={totals['docs_done']:,} fetched={totals['fetched']:,} "
        f"cached={totals['cached']:,} no_photo={totals['no_photo']:,} "
        f"errors={totals['errors']:,} updated_rows={totals['updated_rows']:,}"
    )
    return totals
