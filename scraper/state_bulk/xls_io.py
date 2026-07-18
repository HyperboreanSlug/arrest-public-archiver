"""Read IDOC-style XLS/XLSX tables (header row after title banner)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence


def _open_rows(path: Path) -> List[Sequence[Any]]:
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        import openpyxl

        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        return list(ws.iter_rows(values_only=True))
    import xlrd

    book = xlrd.open_workbook(str(path))
    sh = book.sheet_by_index(0)
    return [tuple(sh.cell_value(r, c) for c in range(sh.ncols)) for r in range(sh.nrows)]


def _is_header_row(cells: Sequence[Any], required: Sequence[str]) -> bool:
    texts = [str(c or "").strip().lower() for c in cells]
    joined = " | ".join(texts)
    return all(req.lower() in joined for req in required)


def iter_named_rows(
    path: Path | str,
    *,
    required_headers: Sequence[str] = ("name", "race"),
    max_scan: int = 30,
) -> Iterator[Dict[str, Any]]:
    """
    Yield dict rows from an IDOC-style spreadsheet.

    Skips title/instruction rows; uses the first row that contains required headers.
    """
    path = Path(path)
    rows = _open_rows(path)
    header_idx: Optional[int] = None
    headers: List[str] = []
    for i, row in enumerate(rows[:max_scan]):
        if _is_header_row(row, required_headers):
            header_idx = i
            headers = []
            for j, cell in enumerate(row):
                name = str(cell or "").strip()
                if not name:
                    name = f"col_{j}"
                # de-dupe
                base = name
                n = 2
                while name in headers:
                    name = f"{base}_{n}"
                    n += 1
                headers.append(name)
            break
    if header_idx is None:
        raise ValueError(f"No header row with {required_headers} in {path}")

    for row in rows[header_idx + 1 :]:
        if not row or all(c is None or str(c).strip() == "" for c in row):
            continue
        rec: Dict[str, Any] = {}
        for i, key in enumerate(headers):
            rec[key] = row[i] if i < len(row) else None
        # Skip empty name rows
        name = rec.get("Name") or rec.get("name")
        if name is None or str(name).strip() == "":
            continue
        yield rec
