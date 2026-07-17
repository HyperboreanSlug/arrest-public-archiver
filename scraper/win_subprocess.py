"""Hide Windows console windows for background subprocesses.

GUI apps (pythonw) must not flash black consoles when spawning pip, git, gh,
or helper scripts. Use :func:`no_window_flags` / :func:`run_kwargs` on every
app-spawned subprocess.
"""
from __future__ import annotations

import subprocess
import sys
from typing import Any, Dict


def no_window_flags() -> int:
    """``CREATE_NO_WINDOW`` on Windows; 0 elsewhere."""
    if sys.platform == "win32":
        return int(getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))
    return 0


def run_kwargs(**extra: Any) -> Dict[str, Any]:
    """Merge caller kwargs with console-hiding creationflags on Windows."""
    kw: Dict[str, Any] = dict(extra)
    flags = no_window_flags()
    if flags:
        kw["creationflags"] = int(kw.get("creationflags") or 0) | flags
    return kw
