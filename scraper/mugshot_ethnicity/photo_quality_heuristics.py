"""Image heuristics: silhouettes, CrimeWatch stock tiles, geometry."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Tuple

# Silhouette heuristic thresholds (white bg + dark outline).
_WHITE_FRAC_MIN = 0.70
_BLACK_FRAC_MIN = 0.05
_MID_FRAC_MAX = 0.10
_STUB_SIZE_MIN = 800
_STUB_SIZE_MAX = 25_000


def heuristic_silhouette(path: Path) -> bool:
    """True if image looks like a white-bg black-outline silhouette stub."""
    try:
        size = path.stat().st_size
    except OSError:
        return False
    if size < _STUB_SIZE_MIN or size > _STUB_SIZE_MAX:
        return False
    try:
        from PIL import Image
    except Exception:
        return False
    try:
        with Image.open(path) as im:
            gray = im.convert("L")
            gray.thumbnail((160, 160))
            try:
                import numpy as np

                arr = np.asarray(gray, dtype=np.uint8)
                n = float(arr.size) or 1.0
                white = float((arr > 240).sum()) / n
                black = float((arr < 40).sum()) / n
                mid = 1.0 - white - black
            except Exception:
                hist = gray.histogram()
                total = float(sum(hist)) or 1.0
                white = sum(hist[241:256]) / total
                black = sum(hist[0:40]) / total
                mid = 1.0 - white - black
        return (
            white >= _WHITE_FRAC_MIN
            and black >= _BLACK_FRAC_MIN
            and mid <= _MID_FRAC_MAX
        )
    except Exception:
        return False


def heuristic_gray_placeholder_from_rgb(arr) -> bool:
    """True for nearly uniform mid-gray 'photo not available' tiles."""
    try:
        import numpy as np

        a = np.asarray(arr, dtype=np.float32)
        if a.ndim != 3 or a.shape[2] < 3:
            return False
        r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
        if float(np.mean(np.abs(r - g))) > 8.0 or float(np.mean(np.abs(g - b))) > 8.0:
            return False
        gray = (r + g + b) / 3.0
        mean, std = float(np.mean(gray)), float(np.std(gray))
        if not (175.0 <= mean <= 235.0) or std > 28.0:
            return False
        n = float(gray.size) or 1.0
        return float(((gray >= 170) & (gray <= 245)).sum()) / n >= 0.90
    except Exception:
        return False


def heuristic_gray_placeholder(path: Path) -> bool:
    """True if on-disk image is a gray no-photo placeholder tile."""
    try:
        size = path.stat().st_size
    except OSError:
        return False
    if size < _STUB_SIZE_MIN or size > _STUB_SIZE_MAX:
        return False
    try:
        from PIL import Image

        with Image.open(path) as im:
            arr = rgb_arrays_from_image(im)
            return bool(arr is not None and heuristic_gray_placeholder_from_rgb(arr))
    except Exception:
        return False


def rgb_arrays_from_image(im) -> Optional[Any]:
    try:
        import numpy as np

        return np.asarray(im.convert("RGB"), dtype=np.uint8)
    except Exception:
        return None


def heuristic_crimewatch_stock_from_rgb(arr) -> bool:
    """True for CrimeWatch / RecentlyBooked stock 'ARREST' handcuffs tiles."""
    try:
        h, w = int(arr.shape[0]), int(arr.shape[1])
    except Exception:
        return False
    if min(h, w) < 180 or max(h, w) > 420:
        return False
    y0 = int(h * 0.78)
    bot = arr[y0:, :, :]
    if bot.size == 0:
        return False
    r = bot[:, :, 0].astype("float32")
    g = bot[:, :, 1].astype("float32")
    b = bot[:, :, 2].astype("float32")
    n_bot = float(r.size) or 1.0
    blue_frac = float(((b > r + 20) & (b > g + 10) & (b > 80)).sum()) / n_bot
    gray = (
        0.299 * arr[:, :, 0].astype("float32")
        + 0.587 * arr[:, :, 1].astype("float32")
        + 0.114 * arr[:, :, 2].astype("float32")
    )
    n = float(gray.size) or 1.0
    dark_frac = float((gray < 50).sum()) / n
    bl = arr[int(h * 0.78) : int(h * 0.95), 0 : max(1, int(w * 0.28)), :]
    bl_r = bl[:, :, 0].astype("float32")
    bl_g = bl[:, :, 1].astype("float32")
    bl_b = bl[:, :, 2].astype("float32")
    n_bl = float(bl_r.size) or 1.0
    red_badge = float(
        ((bl_r > 120) & (bl_r > bl_g + 40) & (bl_r > bl_b + 40)).sum()
    ) / n_bl
    return blue_frac >= 0.30 and dark_frac >= 0.45 and red_badge >= 0.04


def heuristic_crimewatch_stock(path: Path) -> bool:
    """True if on-disk image matches the CrimeWatch stock ARREST tile."""
    try:
        size = path.stat().st_size
    except OSError:
        return False
    if size < 200 or size > 40_000:
        return False
    try:
        from PIL import Image
    except Exception:
        return False
    try:
        with Image.open(path) as im:
            arr = rgb_arrays_from_image(im)
            if arr is None:
                return False
            return heuristic_crimewatch_stock_from_rgb(arr)
    except Exception:
        return False


def image_dims(path: Path) -> Optional[Tuple[int, int]]:
    try:
        from PIL import Image

        with Image.open(path) as im:
            w, h = im.size
            return int(w), int(h)
    except Exception:
        return None


def dims_from_bytes(data: bytes) -> Optional[Tuple[int, int]]:
    try:
        from PIL import Image
        import io

        with Image.open(io.BytesIO(data)) as im:
            w, h = im.size
            return int(w), int(h)
    except Exception:
        return None


def geometry_reason(w: int, h: int, size: int, *, ext: str = "") -> Optional[str]:
    """Classify non-mugshot geometry. Returns reason or None if OK."""
    if w < 1 or h < 1:
        return "invalid image dimensions"
    if min(w, h) <= 2:
        return "1×1 or spacer pixel"
    if min(w, h) < 40 and max(w, h) < 120:
        return "tiny icon (not a mugshot)"
    ratio = max(w, h) / float(min(w, h))
    if ratio >= 2.4 and min(w, h) < 120:
        return "banner / strip chrome"
    if ext == ".gif" and size < 4_000 and min(w, h) < 80:
        return "small GIF stub"
    return None
