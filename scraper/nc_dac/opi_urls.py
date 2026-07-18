"""NC DAC OPI public URL builders (detail + mugshot)."""
from __future__ import annotations

from typing import Optional

OPI_HOST = "https://webapps.doc.state.nc.us/opi"


def normalize_doc(doc: Optional[str]) -> Optional[str]:
    """Normalize DOC number to zero-padded 7 digits when numeric."""
    raw = (doc or "").strip()
    if not raw:
        return None
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        return raw[:16]
    try:
        return f"{int(digits):07d}"
    except ValueError:
        return digits[:16]


def detail_url(doc: str) -> str:
    d = normalize_doc(doc) or doc
    return f"{OPI_HOST}/viewoffender.do?method=view&offenderID={d}"


def picture_url(doc: str, *, sequence: int = 1) -> str:
    d = normalize_doc(doc) or doc
    return (
        f"{OPI_HOST}/viewpicture.do"
        f"?method=view&showDate=N&pictureType=I"
        f"&pictureSequence={int(sequence)}&offenderID={d}"
    )
