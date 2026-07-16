"""Import an offline HTTrack (or similar) RecentlyBooked.com mirror."""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Set
from urllib.parse import urlparse

from scraper.charge_classifications import classify_record
from scraper.mugshot_ethnicity.photo_quality import (
    is_placeholder_photo,
    is_placeholder_photo_url,
)

from .archive_html import archive_html
from .parse import parse_detail
from .parse_util import BASE_URL

ProgressCb = Optional[Callable[[int, Dict[str, Any]], None]]

_SITE_DIR = "https@recentlybooked.com"
_STATE_RE = re.compile(r"^[a-z]{2}$", re.I)
_SKIP_TOP = frozenset(
    {
        "css",
        "js",
        "images",
        "mostwanted",
        "about",
        "contact",
        "search",
        "faqs",
        "disclaimer",
        "dmca",
        "mugshot-removal-policy",
    }
)
_BATCH = 200


def resolve_site_root(mirror_root: Path | str) -> Path:
    """Return the site root (folder that holds ``al/``, ``images/``, …)."""
    root = Path(mirror_root)
    if not root.is_dir():
        raise FileNotFoundError(f"Mirror path not found: {root}")
    if (root / "images").is_dir() and any(
        d.is_dir() and _is_state_name(d.name) for d in root.iterdir()
    ):
        return root
    nested = root / _SITE_DIR
    if nested.is_dir():
        return nested
    # HTTrack sometimes nests under https@host only one level down.
    for child in root.iterdir():
        if child.is_dir() and child.name.startswith("https@"):
            return child
    raise FileNotFoundError(
        f"No RecentlyBooked site root under {root} "
        f"(expected {_SITE_DIR}/ or state folders + images/)"
    )


def _is_state_name(name: str) -> bool:
    return bool(_STATE_RE.match(name)) and name.lower() not in _SKIP_TOP


def iter_detail_paths(
    site_root: Path,
    *,
    state: Optional[str] = None,
    county: Optional[str] = None,
) -> Iterator[Path]:
    """Yield detail page files (slug contains ``~``)."""
    states: List[Path]
    if state:
        st = site_root / state.lower()
        states = [st] if st.is_dir() else []
    else:
        states = sorted(
            p for p in site_root.iterdir() if p.is_dir() and _is_state_name(p.name)
        )
    for st_dir in states:
        if county:
            counties = [st_dir / county.lower()]
        else:
            counties = sorted(p for p in st_dir.iterdir() if p.is_dir())
        for co_dir in counties:
            if not co_dir.is_dir():
                continue
            for f in co_dir.iterdir():
                if f.is_file() and "~" in f.name:
                    yield f


def _url_for_detail(path: Path, site_root: Path) -> str:
    rel = path.relative_to(site_root).as_posix()
    return f"{BASE_URL}/{rel}"


def _local_image(site_root: Path, photo_url: str) -> Optional[Path]:
    if not photo_url or is_placeholder_photo_url(photo_url):
        return None
    path = urlparse(photo_url).path  # /images/728/329442.webp
    if not path.startswith("/images/"):
        return None
    local = site_root / path.lstrip("/")
    if local.is_file() and not is_placeholder_photo(local):
        return local
    return None


def _archive_photo(
    src: Path,
    record: Dict[str, Any],
    output_root: Path,
) -> Optional[Path]:
    state = str(record.get("state") or "xx").lower() or "xx"
    county = str(record.get("county") or "unknown").lower() or "unknown"
    booking_id = str(
        record.get("booking_id") or record.get("source_id") or src.stem
    ).strip() or "unknown"
    dest = output_root / state / county / f"{booking_id}.webp"
    if dest.is_file() and not is_placeholder_photo(dest):
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        try:
            dest.unlink()
        except OSError:
            pass
    shutil.copy2(src, dest)
    if is_placeholder_photo(dest):
        try:
            dest.unlink()
        except OSError:
            pass
        return None
    return dest


def parse_detail_file(
    path: Path,
    site_root: Path,
    *,
    with_photos: bool = True,
    with_html: bool = True,
    photo_root: Path = Path("data/photos/recentlybooked"),
    html_root: Path = Path("data/html/recentlybooked"),
) -> Dict[str, Any]:
    """Parse one mirror detail file into a DB-ready record dict."""
    html = path.read_text(encoding="utf-8", errors="replace")
    source_url = _url_for_detail(path, site_root)
    record = parse_detail(html, source_url)
    if with_html:
        html_path = archive_html(html, record, output_root=html_root)
        if html_path:
            record["html_path"] = str(html_path)
    if with_photos:
        src = _local_image(site_root, str(record.get("photo_url") or ""))
        if src is None:
            # Construct from facility + booking_id when img is missing/rewritten.
            fac = str(record.get("facility") or "").strip()
            bid = str(record.get("booking_id") or "").strip()
            if fac and bid:
                cand = site_root / "images" / fac / f"{bid}.webp"
                if cand.is_file() and not is_placeholder_photo(cand):
                    src = cand
                    record["photo_url"] = f"{BASE_URL}/images/{fac}/{bid}.webp"
        if src is not None:
            photo_path = _archive_photo(src, record, Path(photo_root))
            if photo_path:
                record["photo_path"] = str(photo_path)
    classify_record(record)
    return record


def import_mirror(
    mirror_root: Path | str,
    db: Any,
    *,
    state: Optional[str] = None,
    county: Optional[str] = None,
    limit: int = 0,
    with_photos: bool = True,
    with_html: bool = True,
    skip_existing_urls: bool = True,
    require_photo: bool = True,
    photo_root: Path | str = Path("data/photos/recentlybooked"),
    html_root: Path | str = Path("data/html/recentlybooked"),
    progress_cb: ProgressCb = None,
) -> Dict[str, int]:
    """Walk a disk mirror, parse details, archive assets, import into *db*."""
    site_root = resolve_site_root(mirror_root)
    existing: Set[str] = set()
    if skip_existing_urls:
        existing = set(db.existing_source_urls() or set())

    stats = {
        "seen": 0,
        "parsed": 0,
        "imported": 0,
        "skipped": 0,
        "rejected_no_photo": 0,
        "errors": 0,
    }
    batch: List[Dict[str, Any]] = []
    photo_root_p = Path(photo_root)
    html_root_p = Path(html_root)

    def flush() -> None:
        if not batch:
            return
        r = db.import_records(
            batch,
            skip_existing_urls=skip_existing_urls,
            require_photo=require_photo,
        )
        stats["imported"] += int(r.get("imported") or 0)
        stats["skipped"] += int(r.get("skipped") or 0)
        stats["rejected_no_photo"] += int(r.get("rejected_no_photo") or 0)
        batch.clear()

    for path in iter_detail_paths(site_root, state=state, county=county):
        if limit and stats["seen"] >= limit:
            break
        stats["seen"] += 1
        source_url = _url_for_detail(path, site_root)
        if skip_existing_urls and source_url in existing:
            stats["skipped"] += 1
            if progress_cb and stats["seen"] % 500 == 0:
                progress_cb(stats["seen"], dict(stats))
            continue
        try:
            rec = parse_detail_file(
                path,
                site_root,
                with_photos=with_photos,
                with_html=with_html,
                photo_root=photo_root_p,
                html_root=html_root_p,
            )
        except Exception:
            stats["errors"] += 1
            continue
        stats["parsed"] += 1
        url = str(rec.get("source_url") or "")
        if url:
            existing.add(url)
        batch.append(rec)
        if len(batch) >= _BATCH:
            flush()
        if progress_cb and stats["seen"] % 200 == 0:
            progress_cb(stats["seen"], dict(stats))

    flush()
    if progress_cb:
        progress_cb(stats["seen"], dict(stats))
    return stats
