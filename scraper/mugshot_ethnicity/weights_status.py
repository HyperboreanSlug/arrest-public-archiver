"""Local download status helpers for DeepFace weights / detectors."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Sequence, Tuple

from scraper.mugshot_ethnicity.weights_data import (
    DETECTOR_CACHE_FILES,
    WEIGHT_CACHE_FILES,
    _MIN_BYTES,
)


def weights_dir() -> Path:
    """DeepFace local weight cache directory."""
    home = os.environ.get("DEEPFACE_HOME") or str(Path.home() / ".deepface")
    return Path(home) / "weights"


def _files_present(names: Sequence[str], *, min_bytes: int = _MIN_BYTES) -> Tuple[bool, int]:
    """Return (all present & large enough, total bytes)."""
    if not names:
        return True, 0
    root = weights_dir()
    total = 0
    for name in names:
        p = root / name
        try:
            if not p.is_file():
                return False, total
            sz = p.stat().st_size
            if sz < min_bytes:
                return False, total
            total += sz
        except OSError:
            return False, total
    return True, total


def _fmt_mb(nbytes: int) -> str:
    if nbytes <= 0:
        return ""
    mb = nbytes / (1024 * 1024)
    if mb >= 100:
        return f"{mb:.0f} MB"
    if mb >= 10:
        return f"{mb:.1f} MB"
    if mb >= 1:
        return f"{mb:.1f} MB"
    kb = nbytes / 1024
    return f"{kb:.0f} KB"


def weight_local_status(model_id: str) -> Dict[str, Any]:
    """
    Local download status for a weight model id (Race, ArcFace, …).

    Keys: downloaded (bool), builtin (bool), bytes (int), files (list),
    label (short UI string), detail (longer).
    """
    names = list(WEIGHT_CACHE_FILES.get(model_id) or [])
    if not names:
        return {
            "downloaded": False,
            "builtin": False,
            "bytes": 0,
            "files": [],
            "label": "Unknown model",
            "detail": f"No cache mapping for {model_id}",
        }
    ok, total = _files_present(names)
    size_s = _fmt_mb(total)
    if ok:
        return {
            "downloaded": True,
            "builtin": False,
            "bytes": total,
            "files": names,
            "label": f"Downloaded ({size_s})" if size_s else "Downloaded",
            "detail": f"Present in {weights_dir()}: {', '.join(names)}",
        }
    return {
        "downloaded": False,
        "builtin": False,
        "bytes": total,
        "files": names,
        "label": "Not downloaded",
        "detail": f"Missing under {weights_dir()}: {', '.join(names)}",
    }


def detector_local_status(det_id: str) -> Dict[str, Any]:
    """Local download status for a face detector id."""
    det = (det_id or "").strip().lower()
    if det not in DETECTOR_CACHE_FILES:
        return {
            "downloaded": False,
            "builtin": False,
            "bytes": 0,
            "files": [],
            "label": "Unknown detector",
            "detail": f"No cache mapping for {det_id}",
        }
    names = list(DETECTOR_CACHE_FILES[det])
    if not names:
        # Built-in (opencv) or package-bundled (mtcnn)
        if det == "opencv":
            return {
                "downloaded": True,
                "builtin": True,
                "bytes": 0,
                "files": [],
                "label": "Built-in",
                "detail": "No DeepFace weight file; uses OpenCV Haar cascades",
            }
        return {
            "downloaded": True,
            "builtin": True,
            "bytes": 0,
            "files": [],
            "label": "Package-bundled",
            "detail": "Weights ship with the Python package (not in ~/.deepface/weights)",
        }
    ok, total = _files_present(names)
    size_s = _fmt_mb(total)
    if ok:
        return {
            "downloaded": True,
            "builtin": False,
            "bytes": total,
            "files": names,
            "label": f"Downloaded ({size_s})" if size_s else "Downloaded",
            "detail": f"Present in {weights_dir()}: {', '.join(names)}",
        }
    return {
        "downloaded": False,
        "builtin": False,
        "bytes": total,
        "files": names,
        "label": "Not downloaded",
        "detail": f"Missing under {weights_dir()}: {', '.join(names)}",
    }


def all_weight_local_status() -> Dict[str, Dict[str, Any]]:
    return {mid: weight_local_status(mid) for mid in WEIGHT_CACHE_FILES}


def all_detector_local_status() -> Dict[str, Dict[str, Any]]:
    return {did: detector_local_status(did) for did in DETECTOR_CACHE_FILES}


def detector_dropdown_label(d: Dict[str, Any], *, include_status: bool = True) -> str:
    """Compact combo-box line: name + VRAM + download status."""
    short = d.get("vram_short") or d.get("vram") or ""
    base = d.get("label") or d.get("id") or ""
    parts = [base]
    if short:
        parts.append(short)
    if include_status:
        try:
            st = detector_local_status(str(d.get("id") or ""))
            if st.get("downloaded"):
                if st.get("builtin"):
                    parts.append(str(st.get("label") or "Built-in"))
                else:
                    parts.append("✓ " + str(st.get("label") or "Downloaded"))
            else:
                parts.append("not downloaded")
        except Exception:
            pass
    return "  ·  ".join(parts)
