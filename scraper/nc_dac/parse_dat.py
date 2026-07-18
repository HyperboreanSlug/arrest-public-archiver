"""Stream fixed-width NC DAC .dat rows using a .des layout."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterator, List, Optional

from scraper.nc_dac.layout import Field, parse_des, record_width


def _clean(value: str) -> Optional[str]:
    text = (value or "").strip()
    if not text:
        return None
    # Converted/unknown placeholders in historical rows
    if set(text) <= {"?", "*"}:
        return None
    if text in ("0001-01-01", "9999-12-31"):
        return None
    return text


def parse_line(line: str, fields: List[Field]) -> Dict[str, Optional[str]]:
    row: Dict[str, Optional[str]] = {}
    raw = line.rstrip("\r\n")
    for f in fields:
        lo, hi = f.slice
        chunk = raw[lo:hi] if lo < len(raw) else ""
        row[f.name] = _clean(chunk)
    return row


def iter_dat(
    dat_path: Path,
    des_path: Optional[Path] = None,
    *,
    fields: Optional[List[Field]] = None,
    limit: int = 0,
) -> Iterator[Dict[str, Optional[str]]]:
    """Yield dict rows from a .dat file. limit=0 means all rows."""
    if fields is None:
        if des_path is None:
            des_path = dat_path.with_suffix(".des")
        fields = parse_des(des_path)
    if not fields:
        raise ValueError(f"No layout fields for {dat_path}")
    _ = record_width(fields)
    n = 0
    with dat_path.open("r", encoding="latin-1", errors="replace") as fh:
        for line in fh:
            if not line.strip():
                continue
            yield parse_line(line, fields)
            n += 1
            if limit and n >= limit:
                return


def load_index_by_key(
    dat_path: Path,
    key_field: str,
    value_fields: List[str],
    des_path: Optional[Path] = None,
) -> Dict[str, Dict[str, Optional[str]]]:
    """Build DOC-id → selected fields map (for enrichment joins)."""
    fields = parse_des(des_path or dat_path.with_suffix(".des"))
    want = {key_field.upper(), *(v.upper() for v in value_fields)}
    slim = [f for f in fields if f.name.upper() in want]
    if not slim:
        return {}
    out: Dict[str, Dict[str, Optional[str]]] = {}
    for row in iter_dat(dat_path, fields=fields):
        key = row.get(key_field) or row.get(key_field.upper())
        if not key:
            # try exact name from layout
            for k, v in row.items():
                if k.upper() == key_field.upper() and v:
                    key = v
                    break
        if not key:
            continue
        out[str(key)] = {
            f.name: row.get(f.name) for f in slim if f.name.upper() != key_field.upper()
        }
    return out
