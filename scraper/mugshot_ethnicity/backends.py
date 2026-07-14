"""Pluggable *local* mugshot ethnicity backends (lazy imports).

Production default is **DeepFace** (https://github.com/serengil/deepface):
open-source, runs entirely on-machine, downloads model weights once into the
user cache. It exposes a dedicated race attribute model (White / Black / Asian /
Indian / Middle Eastern / Latino Hispanic) which is what we need for
high-confidence gross misclassification checks.

Optional fallbacks:
  - CLIP zero-shot (local transformers + torch) if DeepFace is not installed
  - MockBackend for unit tests only (never selected by ``auto``)
"""
from __future__ import annotations

from typing import Dict, List, Type

from scraper.mugshot_ethnicity.backends_base import EthnicityBackend, MockBackend
from scraper.mugshot_ethnicity.backends_clip import ClipBackend
from scraper.mugshot_ethnicity.backends_deepface import DeepFaceBackend

# Production backends only — mock is never in auto chain
_BACKEND_CLASSES: List[Type[EthnicityBackend]] = [
    DeepFaceBackend,
    ClipBackend,
]


def list_backend_status() -> Dict[str, bool]:
    """Fast presence check via find_spec — never import torch/keras on the UI thread."""
    import importlib.util

    out: Dict[str, bool] = {"mock": True}
    try:
        out["deepface"] = importlib.util.find_spec("deepface") is not None
    except Exception:
        out["deepface"] = False
    try:
        out["clip"] = (
            importlib.util.find_spec("torch") is not None
            and importlib.util.find_spec("transformers") is not None
        )
    except Exception:
        out["clip"] = False
    return out


def create_backend(
    name: str = "auto",
    *,
    auto_install: bool = True,
    log=None,
) -> EthnicityBackend:
    """
    Create a backend by name.

    ``auto`` / ``deepface`` → ensure DeepFace is installed (pip + model warm-up)
    then use it. Falls back to CLIP only if DeepFace setup fails.
    ``mock`` → tests only (never auto-installed as production).
    """
    from scraper.mugshot_ethnicity.setup import ensure_deepface

    key = (name or "auto").strip().lower()
    if key == "mock":
        return MockBackend()

    if key in ("auto", "deepface"):
        # Auto-install DeepFace into this interpreter when missing
        if auto_install:
            ensure_deepface(auto_install=True, warm=True, log=log)
        b = DeepFaceBackend()
        if b.is_available():
            return b
        if key == "deepface":
            raise RuntimeError(
                "DeepFace could not be set up automatically.\n"
                f"Interpreter: {__import__('sys').executable}\n"
                "Try:\n"
                "  python -m pip install -r requirements-vision.txt\n"
                "Or set SOR_SKIP_DEEPFACE_INSTALL=1 only to disable auto-install."
            )
        # auto: try CLIP before giving up
        try:
            c = ClipBackend()
            if c.is_available():
                return c
        except Exception:
            pass
        status = list_backend_status()
        raise RuntimeError(
            "No local vision backend available after DeepFace auto-setup.\n"
            f"Status: {status}\n"
            "  python -m pip install -r requirements-vision.txt"
        )

    if key == "clip":
        b = ClipBackend()
        if not b.is_available():
            raise RuntimeError(
                "CLIP backend not installed:\n"
                "  pip install torch transformers pillow"
            )
        return b
    raise ValueError(f"Unknown mugshot backend: {name!r}")


__all__ = [
    "EthnicityBackend",
    "MockBackend",
    "DeepFaceBackend",
    "ClipBackend",
    "list_backend_status",
    "create_backend",
    "_BACKEND_CLASSES",
]
