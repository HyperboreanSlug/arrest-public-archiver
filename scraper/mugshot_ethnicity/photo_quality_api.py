"""Public photo-quality API: classify paths/bytes, resolve photo paths."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Union

from scraper.mugshot_ethnicity.photo_quality_hashes import (
    KNOWN_CHROME_MD5,
    KNOWN_PLACEHOLDER_MD5,
    file_md5,
    is_placeholder_photo_url,
    md5_bytes,
    url_looks_like_chrome,
)
from scraper.mugshot_ethnicity.photo_quality_heuristics import (
    _MID_FRAC_MAX,
    _STUB_SIZE_MAX,
    _STUB_SIZE_MIN,
    _BLACK_FRAC_MIN,
    _WHITE_FRAC_MIN,
    dims_from_bytes,
    geometry_reason,
    heuristic_crimewatch_stock,
    heuristic_crimewatch_stock_from_rgb,
    heuristic_silhouette,
    image_dims,
    rgb_arrays_from_image,
)


def record_has_real_photo(record: Optional[Mapping[str, Any]]) -> bool:
    """True when *record* has a real mugshot file on disk (not missing/placeholder)."""
    if not record:
        return False
    url = str(record.get("photo_url") or "").strip()
    if url and is_placeholder_photo_url(url):
        return False
    path = str(record.get("photo_path") or "").strip()
    if not path:
        return False
    p = resolve_photo_path(path)
    if p is None:
        raw = Path(path)
        if not raw.is_file():
            return False
        p = raw
    return not is_placeholder_photo(p)


@lru_cache(maxsize=16384)
def _classify_cached(resolved: str, mtime_ns: int, size: int) -> Optional[str]:
    path = Path(resolved)
    digest = file_md5(path)
    if digest and digest in KNOWN_PLACEHOLDER_MD5:
        return "registry silhouette placeholder (known stub)"
    if digest and digest in KNOWN_CHROME_MD5:
        return "site chrome (known non-mugshot)"
    if heuristic_crimewatch_stock(path):
        return "CrimeWatch / stock ARREST placeholder (not a mugshot)"
    if heuristic_silhouette(path):
        return "registry silhouette placeholder (white bg + outline)"
    dims = image_dims(path)
    if dims is None:
        return None
    w, h = dims
    return geometry_reason(w, h, size, ext=path.suffix.lower())


def non_mugshot_reason(path: Union[str, Path, None]) -> Optional[str]:
    if path is None:
        return None
    raw = str(path).strip()
    if not raw:
        return None
    p = Path(raw)
    if not p.is_file():
        return None
    try:
        st = p.stat()
        resolved = str(p.resolve())
        return _classify_cached(
            resolved, int(getattr(st, "st_mtime_ns", 0)), int(st.st_size)
        )
    except OSError:
        return None


def is_non_mugshot(path: Union[str, Path, None]) -> bool:
    return non_mugshot_reason(path) is not None


def placeholder_reason(path: Union[str, Path, None]) -> Optional[str]:
    return non_mugshot_reason(path)


def is_placeholder_photo(path: Union[str, Path, None]) -> bool:
    return is_non_mugshot(path)


def bytes_non_mugshot_reason(data: bytes, *, url: str = "", ext: str = "") -> Optional[str]:
    if not data:
        return "empty image body"
    if len(data) < 40:
        return "image too small"
    digest = md5_bytes(data)
    if digest in KNOWN_PLACEHOLDER_MD5:
        return "registry silhouette placeholder (known stub)"
    if digest in KNOWN_CHROME_MD5:
        return "site chrome (known non-mugshot)"
    if url_looks_like_chrome(url):
        return "chrome URL pattern"
    e = (ext or "").lower()
    if not e:
        if data[:3] == b"\xff\xd8\xff":
            e = ".jpg"
        elif data[:8] == b"\x89PNG\r\n\x1a\n":
            e = ".png"
        elif data[:6] in (b"GIF87a", b"GIF89a"):
            e = ".gif"
        elif data[:4] == b"RIFF" and len(data) > 12 and data[8:12] == b"WEBP":
            e = ".webp"
    dims = dims_from_bytes(data)
    if dims is None:
        return None
    w, h = dims
    geo = geometry_reason(w, h, len(data), ext=e)
    if geo:
        return geo
    if 200 <= len(data) <= 40_000:
        try:
            from PIL import Image
            import io

            with Image.open(io.BytesIO(data)) as im:
                arr = rgb_arrays_from_image(im)
                if arr is not None and heuristic_crimewatch_stock_from_rgb(arr):
                    return "CrimeWatch / stock ARREST placeholder (not a mugshot)"
        except Exception:
            pass
    if _STUB_SIZE_MIN <= len(data) <= _STUB_SIZE_MAX:
        try:
            from PIL import Image
            import io

            with Image.open(io.BytesIO(data)) as im:
                gray = im.convert("L")
                gray.thumbnail((160, 160))
                hist = gray.histogram()
                total = float(sum(hist)) or 1.0
                white = sum(hist[241:256]) / total
                black = sum(hist[0:40]) / total
                mid = 1.0 - white - black
                if (
                    white >= _WHITE_FRAC_MIN
                    and black >= _BLACK_FRAC_MIN
                    and mid <= _MID_FRAC_MAX
                ):
                    return "registry silhouette placeholder (white bg + outline)"
        except Exception:
            pass
    return None


def clear_placeholder_cache() -> None:
    _classify_cached.cache_clear()


def resolve_photo_path(
    raw: Union[str, Path, None],
    *,
    extra_roots: Optional[Sequence[Union[str, Path]]] = None,
) -> Optional[Path]:
    from scraper.mugshot_ethnicity.photo_quality_resolve import resolve_photo_path as _resolve

    return _resolve(raw, extra_roots=extra_roots)
