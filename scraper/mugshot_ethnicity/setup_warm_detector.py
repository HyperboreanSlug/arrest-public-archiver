"""Detector warm-up and single-model build helpers."""
from __future__ import annotations

import os
from typing import Any, Callable, Optional

from scraper.mugshot_ethnicity.setup_common import (
    _is_abi_error,
    _log,
    _short_err,
    configure_tf_keras_env,
)


def _model_task(model_id: str) -> str:
    """DeepFace ≥0.0.95 requires an explicit task for build_model."""
    mid = (model_id or "").strip()
    if mid in ("Age", "Gender", "Emotion", "Race"):
        return "facial_attribute"
    detectors = {
        "opencv",
        "ssd",
        "dlib",
        "mtcnn",
        "retinaface",
        "mediapipe",
        "yunet",
        "fastmtcnn",
        "centerface",
        "yolov8",
        "yolov11",
        "yolov12",
    }
    low = mid.lower()
    if low in detectors or low.startswith("yolo"):
        return "face_detector"
    if low in ("fasnet",):
        return "spoofing"
    return "facial_recognition"


def _build_one_model(DeepFace: Any, model_id: str, log: Optional[Callable[[str], None]]) -> bool:
    """Download/build a single DeepFace model by name."""
    _log(log, f"Downloading / building weights: {model_id} …")
    try:
        if not hasattr(DeepFace, "build_model"):
            _log(log, f"  build_model unavailable for {model_id}")
            return False
        task = _model_task(model_id)
        # New API: build_model(model_name, task=...)
        try:
            DeepFace.build_model(model_id, task=task)
            _log(log, f"  OK: {model_id} (task={task})")
            return True
        except TypeError:
            pass
        # Older API: build_model(model_name) only
        try:
            DeepFace.build_model(model_id)
            _log(log, f"  OK: {model_id}")
            return True
        except TypeError:
            DeepFace.build_model(model_name=model_id)
            _log(log, f"  OK: {model_id}")
            return True
    except Exception as e:
        msg = str(e)
        _log(log, f"  FAIL {model_id}: {e}")
        if _is_abi_error(msg):
            raise
        return False


def _warm_detector(
    DeepFace: Any,
    det: str,
    *,
    log: Optional[Callable[[str], None]] = None,
) -> bool:
    """Download detector weights and smoke-test with a tiny image.

    RetinaFace requires TF_USE_LEGACY_KERAS (set by configure_tf_keras_env).
    """
    configure_tf_keras_env()
    det = (det or "opencv").strip().lower() or "opencv"
    _log(log, f"Warming detector backend: {det} …")

    # 1) Prefer explicit build_model (downloads weights without full analyze)
    if det != "opencv":
        try:
            if hasattr(DeepFace, "build_model"):
                try:
                    DeepFace.build_model(det, task="face_detector")
                except TypeError:
                    DeepFace.build_model(det)
            _log(log, f"  OK detector weights: {det}")
        except Exception as e:
            _log(log, f"  Detector build note ({det}): {_short_err(e)}")
            # Still try analyze — some backends only load on first use

    # 2) Smoke-test analyze (proves end-to-end path for race tools)
    try:
        import tempfile

        import numpy as np
        from PIL import Image

        # Slightly larger than 96px — some detectors reject tiny inputs
        arr = np.zeros((160, 160, 3), dtype=np.uint8)
        arr[:] = (180, 140, 120)
        # Draw a simple face-like blob so Haar/SSD have something to find
        arr[40:120, 40:120] = (210, 180, 160)
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            Image.fromarray(arr).save(f.name, format="JPEG")
            path = f.name
        try:
            DeepFace.analyze(
                img_path=path,
                actions=["race"],
                enforce_detection=False,
                detector_backend=det,
                silent=True,
            )
            _log(log, f"  OK detector analyze: {det}")
            return True
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
    except Exception as e:
        msg = _short_err(e)
        # Keras 3 / RetinaFace mismatch — give a clear fix hint
        if "KerasTensor" in str(e) or "legacy" in msg.lower():
            _log(
                log,
                f"  Detector warm failed ({det}): Keras 3 incompatibility. "
                "Restart the app so TF_USE_LEGACY_KERAS=1 is set before TensorFlow loads. "
                f"Detail: {msg}",
            )
        else:
            _log(log, f"  Detector warm note ({det}): {msg}")
        # Race weights alone are still usable with another detector
        if det != "opencv":
            _log(log, "  Tip: try detector “OpenCV Haar” or “SSD” if RetinaFace keeps failing.")
        return False
