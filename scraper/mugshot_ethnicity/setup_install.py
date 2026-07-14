"""ensure_deepface install orchestration."""
from __future__ import annotations

import os
import sys
import threading
from typing import Callable, Optional

from scraper.mugshot_ethnicity.setup_common import (
    _FALLBACK_PACKAGES,
    _LOCK_PATH,
    _ProcessFileLock,
    _VISION_REQ,
    _install_lock,
    _is_abi_error,
    _log,
    _pip_python,
)
from scraper.mugshot_ethnicity.setup_pip import _pip_install, _repair_numpy_stack
from scraper.mugshot_ethnicity.setup_runtime import (
    _clear_ml_modules,
    deepface_importable,
    deepface_runtime_ok,
    invalidate_runtime_cache,
)

# Re-export for setup_warm (and any other callers)
__all_internal__ = ["_repair_numpy_stack", "ensure_deepface", "ensure_deepface_background"]


def ensure_deepface(
    *,
    auto_install: bool = True,
    warm: bool = True,
    log: Optional[Callable[[str], None]] = None,
    force_reinstall: bool = False,
) -> bool:
    """
    Make DeepFace usable in this process.

    1. If runtime-ok → optionally warm race model → True
    2. Else if auto_install → pip install (with lock + ABI repair) → re-check
    3. Else False

    Safe to call repeatedly (install attempted at most once per process unless
    *force_reinstall*).
    """
    import scraper.mugshot_ethnicity.setup_common as _c
    from scraper.mugshot_ethnicity.setup_warm import warm_deepface_models

    runtime_ok, detail = deepface_runtime_ok()
    if runtime_ok and not force_reinstall:
        if warm:
            warm_deepface_models(log=log)
        return True

    # Importable but ABI-broken — still need repair even if "available"
    needs_repair = _is_abi_error(detail) or (
        deepface_importable() and not runtime_ok and "ABI" in detail
    )

    if not auto_install:
        if not runtime_ok:
            _log(log, f"DeepFace not ready: {detail}")
        return False

    with _install_lock:
        if _c._install_attempted and not force_reinstall and not needs_repair:
            ok = bool(_c._install_ok and deepface_runtime_ok()[0])
            if ok and warm:
                warm_deepface_models(log=log)
            return ok

        _c._install_attempted = True

        runtime_ok, detail = deepface_runtime_ok()
        if runtime_ok and not force_reinstall:
            _c._install_ok = True
            if warm:
                warm_deepface_models(log=log)
            return True

        env_skip = os.environ.get("SOR_SKIP_DEEPFACE_INSTALL", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        if env_skip:
            _log(log, "SOR_SKIP_DEEPFACE_INSTALL set — not auto-installing DeepFace")
            _c._install_ok = False
            return False

        _log(log, f"Interpreter: {sys.executable}")
        _log(log, f"Pip target:  {_pip_python()}")
        if detail and detail != "ok":
            _log(log, f"Pre-install status: {detail}")

        try:
            with _ProcessFileLock(_LOCK_PATH, timeout=900.0):
                if needs_repair or force_reinstall or _is_abi_error(detail):
                    ok = _repair_numpy_stack(log=log)
                else:
                    if _VISION_REQ.is_file():
                        ok = _pip_install(
                            ["-r", str(_VISION_REQ)],
                            log=log,
                            force_reinstall=force_reinstall,
                            retries=3,
                        )
                    else:
                        ok = _pip_install(
                            list(_FALLBACK_PACKAGES),
                            log=log,
                            force_reinstall=force_reinstall,
                            retries=3,
                        )
                    _clear_ml_modules()
                    invalidate_runtime_cache()
                    runtime_ok, detail = deepface_runtime_ok(force=True)
                    if ok and not runtime_ok and (
                        _is_abi_error(detail) or "ABI" in detail or not deepface_importable()
                    ):
                        _log(log, f"Post-install check failed ({detail}) — running ABI repair")
                        ok = _repair_numpy_stack(log=log)
        except TimeoutError as e:
            _log(log, str(e))
            ok = False
        except Exception as e:
            _log(log, f"DeepFace install lock error: {e}")
            ok = False

        _clear_ml_modules()
        invalidate_runtime_cache()
        runtime_ok, detail = deepface_runtime_ok(force=True)
        _c._install_ok = bool(ok and runtime_ok)
        if not _c._install_ok:
            _log(
                log,
                "DeepFace still not ready after install.\n"
                f"  Detail: {detail}\n"
                f"  Interpreter: {sys.executable}\n"
                "Try manually (close other Python apps first):\n"
                f"  {_pip_python()} -m pip install --user --force-reinstall "
                f"--no-cache-dir -r {_VISION_REQ if _VISION_REQ.is_file() else 'requirements-vision.txt'}",
            )
            return False

        _log(log, "DeepFace runtime OK")
        if warm:
            warm_deepface_models(log=log)
        return True


def ensure_deepface_background(
    *,
    log: Optional[Callable[[str], None]] = None,
) -> threading.Thread:
    """Start ensure_deepface in a daemon thread (non-blocking GUI startup)."""

    def _run() -> None:
        try:
            ensure_deepface(auto_install=True, warm=True, log=log)
        except Exception as e:
            _log(log, f"Background DeepFace setup error: {e}")

    t = threading.Thread(target=_run, name="deepface-setup", daemon=True)
    t.start()
    return t
