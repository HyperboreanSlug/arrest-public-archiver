"""Pip install helpers for the DeepFace vision stack."""
from __future__ import annotations

import os
import subprocess
import time
from typing import Callable, List, Optional

from scraper.mugshot_ethnicity.setup_common import (
    _REPAIR_PACKAGES,
    _in_venv,
    _is_lock_error,
    _log,
    _pip_python,
)
from scraper.mugshot_ethnicity.setup_runtime import (
    _clear_ml_modules,
    invalidate_runtime_cache,
)


def _pip_install(
    packages_or_req: List[str],
    *,
    log: Optional[Callable[[str], None]],
    force_reinstall: bool = False,
    no_cache: bool = False,
    retries: int = 3,
) -> bool:
    """Run pip install into *this* interpreter's environment."""
    py = _pip_python()
    cmd = [py, "-m", "pip", "install", "--upgrade"]
    if force_reinstall:
        cmd.append("--force-reinstall")
    if no_cache:
        cmd.append("--no-cache-dir")
    if not _in_venv():
        cmd.append("--user")
    cmd.extend(packages_or_req)

    for attempt in range(1, max(1, retries) + 1):
        _log(log, f"Installing DeepFace stack (attempt {attempt}/{retries}):\n  {' '.join(cmd)}")
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=int(os.environ.get("SOR_DEEPFACE_PIP_TIMEOUT", "1800")),
            )
        except subprocess.TimeoutExpired:
            _log(log, "DeepFace pip install timed out")
            return False
        except Exception as e:
            _log(log, f"DeepFace pip install failed to start: {e}")
            return False

        out = (proc.stderr or "") + "\n" + (proc.stdout or "")
        if proc.returncode == 0:
            _log(log, "DeepFace packages installed OK")
            return True

        tail = out[-1800:]
        _log(log, f"DeepFace pip install failed (exit {proc.returncode}):\n{tail}")
        if attempt < retries and _is_lock_error(out):
            wait = 4.0 * attempt
            _log(log, f"File lock / permission conflict — retrying in {wait:.0f}s …")
            time.sleep(wait)
            continue
        return False
    return False


def _repair_numpy_stack(*, log: Optional[Callable[[str], None]]) -> bool:
    """Force-reinstall numpy + dependents to fix ABI mismatches."""
    _log(
        log,
        "Repairing vision stack (numpy ABI / binary incompatibility). "
        "This reinstalls numpy, pandas, keras, tensorflow, deepface …",
    )
    ok = _pip_install(
        list(_REPAIR_PACKAGES),
        log=log,
        force_reinstall=True,
        no_cache=True,
        retries=3,
    )
    _clear_ml_modules()
    invalidate_runtime_cache()
    return ok
