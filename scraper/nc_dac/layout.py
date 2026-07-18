"""Parse NC DAC fixed-width .des layout files."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class Field:
    name: str
    description: str
    ftype: str
    start: int  # 1-based inclusive, as published
    length: int

    @property
    def slice(self) -> Tuple[int, int]:
        """0-based half-open slice into a record line."""
        lo = max(0, self.start - 1)
        return lo, lo + max(0, self.length)


def parse_des(path: Path) -> List[Field]:
    """Parse a PublicTables-style .des file into ordered fields."""
    fields: List[Field] = []
    text = path.read_text(encoding="latin-1", errors="replace")
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.lower().startswith("name"):
            continue
        # Columns are space-padded fixed positions in the .des itself:
        # name (0:14), description (14:48), type (48:57), start (57:66), length (66:)
        if len(line) < 60:
            parts = line.split()
            if len(parts) < 5:
                continue
            name, *mid, ftype, start_s, len_s = parts
            desc = " ".join(mid)
            try:
                fields.append(
                    Field(name, desc, ftype, int(start_s), int(len_s))
                )
            except ValueError:
                continue
            continue
        name = line[0:14].strip()
        desc = line[14:48].strip()
        ftype = line[48:57].strip()
        start_s = line[57:66].strip()
        len_s = line[66:].strip()
        if not name or not start_s or not len_s:
            continue
        try:
            fields.append(Field(name, desc, ftype, int(start_s), int(len_s)))
        except ValueError:
            continue
    return fields


def record_width(fields: List[Field]) -> int:
    if not fields:
        return 0
    return max(f.start + f.length - 1 for f in fields)


def fields_by_name(fields: List[Field]) -> Dict[str, Field]:
    return {f.name.upper(): f for f in fields}
