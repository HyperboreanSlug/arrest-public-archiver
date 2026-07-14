"""Strip mugshots.com charges-table UI chrome from scraped charge blobs.

Site often dumps the whole grid as one string, e.g.::

    #1 #2 Charge Description ROBBERY 1ST Offense Date 1/2/2018 ...
    #1 #2 Charge No data to display Count=0 Offense Date Court Type Bond ...
"""
from __future__ import annotations

import re
from typing import Optional

_HASH_RUN = re.compile(r"(?:#\d+\s*)+", re.I)
_NO_DATA = re.compile(r"(?i)no\s+data\s+to\s+display")
_HAS_CHROME = re.compile(
    r"(?i)(?:#\d+\b|charge\s+description|\bcount\s*=\s*\d+|"
    r"offense\s+date|court\s+type|bond\s+type|"
    r"charging\s+agency|arresting\s+agency|attempt\s*/\s*commit)"
)
_TRAIL = re.compile(
    r"(?is)\s+(?:"
    r"count\s*=\s*\d+|"
    r"offense\s+date|"
    r"court\s+type|"
    r"bond\s+type|"
    r"charging\s+agency|"
    r"arresting\s+agency|"
    r"attempt\s*/\s*commit"
    r")\b.*$"
)
_DESC_BODY = re.compile(
    r"(?is)charge\s+description\s+(.+?)(?:"
    r"\s+offense\s+date|"
    r"\s+attempt\s*/\s*commit|"
    r"\s+court\s+type|"
    r"\s+count\s*=|"
    r"\s*$"
    r")"
)
_HASH_CHARGE_BODY = re.compile(
    r"(?is)(?:#\d+\s*)+charge\s+(?!description)(.+?)(?:"
    r"\s+count\s*=|"
    r"\s+offense\s+date|"
    r"\s+court\s+type|"
    r"\s*$"
    r")"
)


def _norm(text: str) -> str:
    return " ".join((text or "").replace("\u00a0", " ").split()).strip(" \t,.;:-")


def has_charge_table_chrome(text: str) -> bool:
    return bool(_HAS_CHROME.search(text or ""))


def strip_charge_table_chrome(text: str) -> str:
    """Return offense text only; empty when the table has no real charges."""
    s = _norm(text)
    if not s:
        return ""
    if _NO_DATA.search(s) and not re.search(
        r"(?i)charge\s+description\s+(?!no\s+data)\S", s
    ):
        # Pure empty grid, or chrome with no real description body.
        if "charge description" not in s.lower():
            return ""

    m = _DESC_BODY.search(s)
    if m:
        body = _norm(m.group(1))
        body = _HASH_RUN.sub("", body).strip()
        if not body or _NO_DATA.search(body):
            return ""
        return _TRAIL.sub("", body).strip(" \t,.;:-")

    m = _HASH_CHARGE_BODY.search(s)
    if m:
        body = _norm(m.group(1))
        if not body or _NO_DATA.search(body):
            return ""
        return _TRAIL.sub("", body).strip(" \t,.;:-")

    if has_charge_table_chrome(s):
        cut = _TRAIL.sub("", s)
        cut = _HASH_RUN.sub("", cut)
        cut = re.sub(r"(?i)^charge\s+description\s+", "", cut)
        cut = re.sub(r"(?i)^charge\s+", "", cut)
        cut = _norm(cut)
        if not cut or _NO_DATA.search(cut):
            return ""
        return cut

    return s
