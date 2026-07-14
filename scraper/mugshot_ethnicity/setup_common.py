"""Shared constants and helpers for DeepFace setup."""
from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional

# Package roots (repo root = parents[2] from this file)
_ROOT = Path(__file__).resolve().parents[2]
_VISION_REQ = _ROOT / "requirements-vision.txt"
_LOCK_PATH = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "sor-public-archiver" / "deepface_pip.lock"

# pip names if requirements-vision.txt is missing
_FALLBACK_PACKAGES = [
    "numpy>=1.26.0,<2.3",
    "deepface>=0.0.93",
    "tensorflow>=2.15.0",
    "tf-keras>=2.15.0",
    "opencv-python>=4.8.0",
    "pillow>=10.0.0",
]

# Packages reinstalled on ABI / binary-incompatibility repair
_REPAIR_PACKAGES = [
    "numpy>=1.26.0,<2.3",
    "pandas",
    "h5py",
    "ml_dtypes",
    "keras",
    "tensorflow>=2.15.0",
    "tf-keras>=2.15.0",
    "deepface>=0.0.93",
    "opencv-python>=4.8.0",
    "pillow>=10.0.0",
]

_install_lock = threading.Lock()
_install_attempted = False
_install_ok: Optional[bool] = None
_warm_attempted = False

# Cache expensive keras/TF probe so the GUI never blocks on every tab click
_runtime_cache_lock = threading.Lock()
_runtime_cache: Optional[tuple] = None
_RUNTIME_CACHE_TTL = 120.0  # seconds


def configure_tf_keras_env() -> None:
    """Must run before any tensorflow/keras import.

    RetinaFace (retina-face package) builds a Functional model with tf.keras /
    tf_keras. Standalone Keras 3 leaves symbolic KerasTensors that cannot be
    fed to TF ops — classic error:

        A KerasTensor cannot be used as input to a TensorFlow function

    TF_USE_LEGACY_KERAS=1 forces TensorFlow to use tf_keras (Keras 2 API).
    """
    os.environ.setdefault("TF_USE_LEGACY_KERAS", "1")
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    # Avoid oneDNN noise / rare numeric issues on CPU
    os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")


# Apply as soon as this module loads (safe if already set)
configure_tf_keras_env()


def _log(log: Optional[Callable[[str], None]], msg: str) -> None:
    if log:
        try:
            log(msg)
        except Exception:
            pass
    else:
        print(msg, flush=True)


def _pip_python() -> str:
    """Interpreter for ``-m pip`` (prefer python.exe over pythonw.exe on Windows)."""
    exe = sys.executable or "python"
    try:
        p = Path(exe)
        name = p.name.lower()
        if name == "pythonw.exe":
            sibling = p.with_name("python.exe")
            if sibling.is_file():
                return str(sibling)
    except Exception:
        pass
    return exe


def _in_venv() -> bool:
    return getattr(sys, "base_prefix", sys.prefix) != sys.prefix or bool(
        os.environ.get("VIRTUAL_ENV")
    )


def _is_lock_error(text: str) -> bool:
    t = (text or "").lower()
    return any(
        s in t
        for s in (
            "winerror 32",
            "being used by another process",
            "cannot access the file",
            "permission denied",
            "[errno 13]",
            "temporarily unavailable",
        )
    )


def _is_abi_error(text: str) -> bool:
    t = (text or "").lower()
    return "numpy.dtype size changed" in t or "binary incompatibility" in t


def _short_err(exc: BaseException, limit: int = 220) -> str:
    msg = str(exc).replace("\n", " ").strip()
    if len(msg) > limit:
        return msg[: limit - 1] + "…"
    return msg


class _ProcessFileLock:
    """Best-effort exclusive lock across processes (Windows + POSIX)."""

    def __init__(self, path: Path, *, timeout: float = 900.0):
        self.path = path
        self.timeout = timeout
        self._fh = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        start = time.time()
        self._fh = open(self.path, "a+", encoding="utf-8")
        while True:
            try:
                if sys.platform == "win32":
                    import msvcrt

                    self._fh.seek(0)
                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._fh.seek(0)
                self._fh.truncate()
                self._fh.write(f"pid={os.getpid()} exe={sys.executable}\n")
                self._fh.flush()
                return self
            except OSError:
                if time.time() - start >= self.timeout:
                    raise TimeoutError(f"Timed out waiting for DeepFace pip lock: {self.path}")
                time.sleep(1.5)

    def __exit__(self, *exc):
        if self._fh is None:
            return
        try:
            if sys.platform == "win32":
                import msvcrt

                self._fh.seek(0)
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            self._fh.close()
        except Exception:
            pass
        self._fh = None
