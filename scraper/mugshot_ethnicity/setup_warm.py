"""DeepFace weight download and model warm-up."""
from __future__ import annotations

from typing import Callable, Dict, List, Optional

from scraper.mugshot_ethnicity.setup_common import (
    _LOCK_PATH,
    _ProcessFileLock,
    _is_abi_error,
    _log,
    configure_tf_keras_env,
)
from scraper.mugshot_ethnicity.setup_runtime import deepface_runtime_ok
from scraper.mugshot_ethnicity.setup_warm_detector import _build_one_model, _warm_detector


def download_selected_weights(
    model_ids: Optional[List[str]] = None,
    *,
    detector_backend: str = "retinaface",
    log: Optional[Callable[[str], None]] = None,
) -> Dict[str, bool]:
    """
    Download selected DeepFace model weights into ``~/.deepface/weights/``.

    Always attempts Race if list is empty. Detectors are exercised via a tiny
    analyze() call so their weights are also fetched when needed.
    """
    from scraper.mugshot_ethnicity.weights_catalog import default_selected_weights

    ok, detail = deepface_runtime_ok()
    if not ok:
        _log(log, f"DeepFace not ready — cannot download weights ({detail})")
        return {}

    models = list(model_ids or default_selected_weights())
    if "Race" not in models:
        models.insert(0, "Race")

    configure_tf_keras_env()
    from deepface import DeepFace

    results: Dict[str, bool] = {}
    for mid in models:
        results[mid] = _build_one_model(DeepFace, mid, log)

    # Warm selected detector: download weights + one analyze pass
    det = (detector_backend or "opencv").strip().lower() or "opencv"
    results[f"detector:{det}"] = _warm_detector(DeepFace, det, log=log)

    ok_n = sum(1 for v in results.values() if v)
    _log(log, f"Weight download finished: {ok_n}/{len(results)} succeeded")
    return results


def warm_deepface_models(
    *,
    log: Optional[Callable[[str], None]] = None,
    model_ids: Optional[List[str]] = None,
    detector_backend: str = "retinaface",
) -> bool:
    """
    Download / load selected models into local cache (default: Race).

    First run may take a few minutes; later runs are fast.
    """
    import scraper.mugshot_ethnicity.setup_common as _c
    from scraper.mugshot_ethnicity.setup_install import _repair_numpy_stack

    ok, detail = deepface_runtime_ok()
    if not ok:
        # Attempt one ABI repair if that is the problem
        if _is_abi_error(detail) or "ABI" in detail:
            _log(log, f"Warm-up blocked ({detail}) — repairing stack first")
            try:
                with _ProcessFileLock(_LOCK_PATH, timeout=900.0):
                    _repair_numpy_stack(log=log)
            except Exception as e:
                _log(log, f"Repair failed: {e}")
                return False
            ok, detail = deepface_runtime_ok()
            if not ok:
                _log(log, f"Still not ready after repair: {detail}")
                return False
        else:
            return False

    # Allow re-warm when explicit model list provided
    if _c._warm_attempted and not model_ids:
        return True
    if not model_ids:
        _c._warm_attempted = True
    try:
        results = download_selected_weights(
            model_ids or ["Race"],
            detector_backend=detector_backend,
            log=log,
        )
        ok = bool(results.get("Race") or any(results.values()))
        if ok:
            _log(log, "DeepFace weights ready under ~/.deepface/weights/")
        return ok
    except Exception as e:
        msg = str(e)
        _log(log, f"DeepFace warm-up failed: {e}")
        if _is_abi_error(msg):
            try:
                with _ProcessFileLock(_LOCK_PATH, timeout=900.0):
                    if _repair_numpy_stack(log=log):
                        _c._warm_attempted = False
                        return warm_deepface_models(
                            log=log,
                            model_ids=model_ids or ["Race"],
                            detector_backend=detector_backend,
                        )
            except Exception as e2:
                _log(log, f"Repair after warm-up failure failed: {e2}")
        return False
