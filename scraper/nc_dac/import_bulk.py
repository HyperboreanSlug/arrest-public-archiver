"""Import NC DAC bulk .dat tables into the MAPA arrests database."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from scraper.nc_dac.map_records import map_inmate_row, map_supervision_row
from scraper.nc_dac.parse_dat import iter_dat, load_index_by_key

DEFAULT_DIR = Path("data/downloads/nc_dac")
INMATE_STEM = "INMT4AA1"
PROFILE_STEM = "OFNT3AA1"
SUPERVISION_STEM = "APPT7AA1"
BATCH = 2000


def _log(msg: str) -> None:
    print(msg, flush=True)


def _resolve_pair(data_dir: Path, stem: str) -> Optional[tuple[Path, Path]]:
    dat = data_dir / f"{stem}.dat"
    des = data_dir / f"{stem}.des"
    if dat.is_file() and des.is_file():
        return dat, des
    return None


def _flush_batch(
    db: Any,
    batch: List[Dict[str, Any]],
    totals: Dict[str, int],
    *,
    force: bool,
) -> None:
    if not batch:
        return
    r = db.import_records(batch, skip_existing_urls=not force)
    totals["imported"] += r.get("imported", 0)
    totals["skipped"] += r.get("skipped", 0)
    totals["skipped_identity"] += r.get("skipped_identity", 0)
    batch.clear()


def import_nc_dac_dir(
    data_dir: Path | str = DEFAULT_DIR,
    *,
    database: Path | str = "data/arrests.db",
    limit: int = 0,
    force: bool = False,
    enrich_profile: bool = True,
    active_only: bool = False,
    include_supervision: bool = True,
    batch_size: int = BATCH,
) -> Dict[str, int]:
    """
    Import NC DAC bulk tables into MAPA.

    Expected files in *data_dir*:
      - INMT4AA1.dat / .des  (required — inmate names + primary offense)
      - OFNT3AA1.dat / .des  (optional — height/weight/hair/eyes)
      - APPT7AA1.dat / .des  (optional — probation/parole clients)
    """
    from scraper.database import Database

    data_dir = Path(data_dir)
    pair = _resolve_pair(data_dir, INMATE_STEM)
    if not pair:
        raise FileNotFoundError(
            f"Need {INMATE_STEM}.dat and .des under {data_dir}. "
            "Download from https://webapps.doc.state.nc.us/opi/downloads.do?method=view"
        )
    dat_path, des_path = pair

    profile_index: Dict[str, Dict[str, Optional[str]]] = {}
    if enrich_profile:
        pp = _resolve_pair(data_dir, PROFILE_STEM)
        if pp:
            _log(f"Loading offender profile index from {pp[0].name} …")
            profile_index = load_index_by_key(
                pp[0],
                "CMDORNUM",
                ["CMCLHITE", "CMWEIGHT", "CMHAIR", "CMCLEYEC", "CMETHNIC"],
                des_path=pp[1],
            )
            _log(f"  profile keys: {len(profile_index):,}")

    db = Database(str(database))
    totals = {
        "read": 0,
        "imported": 0,
        "skipped": 0,
        "skipped_identity": 0,
        "skipped_inactive": 0,
        "no_name": 0,
        "supervision_read": 0,
        "supervision_imported": 0,
    }
    batch: List[Dict[str, Any]] = []

    try:
        _log(f"Reading {dat_path.name} …")
        for row in iter_dat(dat_path, des_path, limit=limit):
            totals["read"] += 1
            if active_only:
                status = (row.get("INMRCDSTA") or row.get("CIINSTAT") or "").upper()
                if status and "INACTIVE" in status:
                    totals["skipped_inactive"] += 1
                    continue
            if not (row.get("CICLSTNM") or row.get("CICFSTNM")):
                totals["no_name"] += 1
                continue
            doc = row.get("CIDORNUM") or ""
            prof = profile_index.get(doc) if profile_index else None
            batch.append(map_inmate_row(row, profile=prof))
            if len(batch) >= batch_size:
                _flush_batch(db, batch, totals, force=force)
                if totals["read"] % 20000 == 0:
                    _log(
                        f"  … read {totals['read']:,}  "
                        f"imported {totals['imported']:,}  "
                        f"skipped {totals['skipped']:,}"
                    )
        _flush_batch(db, batch, totals, force=force)

        if include_supervision:
            sp = _resolve_pair(data_dir, SUPERVISION_STEM)
            if sp:
                _log(f"Reading {sp[0].name} (probation/parole) …")
                for row in iter_dat(sp[0], sp[1], limit=limit):
                    totals["supervision_read"] += 1
                    if active_only:
                        st = (row.get("PPRCDSTA") or row.get("GDSTATUS") or "").upper()
                        if st and "INACTIVE" in st:
                            totals["skipped_inactive"] += 1
                            continue
                    if not (row.get("CDSLSTNM") or row.get("CDSFSTNM")):
                        totals["no_name"] += 1
                        continue
                    batch.append(map_supervision_row(row))
                    if len(batch) >= batch_size:
                        before = totals["imported"]
                        _flush_batch(db, batch, totals, force=force)
                        totals["supervision_imported"] += totals["imported"] - before
                        if totals["supervision_read"] % 20000 == 0:
                            _log(
                                f"  … pp read {totals['supervision_read']:,}  "
                                f"imported total {totals['imported']:,}"
                            )
                before = totals["imported"]
                _flush_batch(db, batch, totals, force=force)
                totals["supervision_imported"] += totals["imported"] - before
    finally:
        db.close()
    return totals
