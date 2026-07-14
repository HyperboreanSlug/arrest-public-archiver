"""DeepFace import / runtime probes and module cache helpers."""
from __future__ import annotations

import importlib
import importlib.util
import sys
import time
from typing import Optional, Tuple

from scraper.mugshot_ethnicity.setup_common import (
    _RUNTIME_CACHE_TTL,
    _runtime_cache_lock,
)


def deepface_importable() -> bool:
    """True if ``import deepface`` would succeed (module present on path)."""
    return importlib.util.find_spec("deepface") is not None


def deepface_available() -> bool:
    """True if the deepface package is on sys.path (fast; no keras/TF load)."""
    return deepface_importable()


def invalidate_runtime_cache() -> None:
    """Clear cached runtime probe (call after install/repair)."""
    import scraper.mugshot_ethnicity.setup_common as _c

    with _runtime_cache_lock:
        _c._runtime_cache = None


def deepface_runtime_ok(*, force: bool = False) -> Tuple[bool, str]:
    """
    Deeper check: numpy + tensorflow/keras path used by DeepFace race models.

    Returns (ok, detail). Catches the common ``numpy.dtype size changed`` ABI
    break that still allows bare ``import deepface`` to succeed.

    Results are cached briefly — keras/TF import can freeze the UI for many
    seconds if called on the main thread.
    """
    import scraper.mugshot_ethnicity.setup_common as _c

    now = time.time()
    if not force:
        with _runtime_cache_lock:
            if _c._runtime_cache is not None:
                ts, ok, detail = _c._runtime_cache
                if now - ts < _RUNTIME_CACHE_TTL:
                    return ok, detail

    if not deepface_importable():
        result = (False, "deepface package not installed")
    else:
        try:
            import numpy as np  # noqa: F401
        except Exception as e:
            result = (False, f"numpy import failed: {e}")
        else:
            try:
                # keras/TF is what actually fails on ABI mismatch (SLOW first time)
                import keras  # noqa: F401
            except Exception as e:
                msg = str(e)
                if "numpy.dtype size changed" in msg or "binary incompatibility" in msg:
                    result = (False, f"numpy ABI mismatch (keras): {msg}")
                else:
                    try:
                        import tensorflow as tf  # noqa: F401
                    except Exception as e2:
                        msg2 = str(e2)
                        if "numpy.dtype size changed" in msg2 or "binary incompatibility" in msg2:
                            result = (False, f"numpy ABI mismatch (tensorflow): {msg2}")
                        else:
                            result = (False, f"tensorflow/keras import failed: {e2}")
                    else:
                        result = (True, "ok")
            else:
                try:
                    import deepface  # noqa: F401
                    result = (True, "ok")
                except Exception as e:
                    result = (False, f"deepface import failed: {e}")

    with _runtime_cache_lock:
        _c._runtime_cache = (time.time(), result[0], result[1])
    return result


def _clear_ml_modules() -> None:
    """Drop cached ML imports so a reinstall is visible in this process."""
    importlib.invalidate_caches()
    prefixes = (
        "deepface",
        "tensorflow",
        "keras",
        "tf_keras",
        "h5py",
        "pandas",
        "cv2",
        "numpy",
        "ml_dtypes",
        "retinaface",
        "mtcnn",
        "gdown",
    )
    for mod in list(sys.modules):
        if mod == "numpy" or any(
            mod == p or mod.startswith(p + ".") for p in prefixes
        ):
            try:
                del sys.modules[mod]
            except KeyError:
                pass
