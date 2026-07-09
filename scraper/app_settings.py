"""Persistent app settings for Arrest Public Archiver."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_SETTINGS_PATH = Path("data/app_settings.json")

DEFAULTS: Dict[str, Any] = {
    "db_path": "data/arrests.db",
    "backup_on_close": False,
    "backup_dir": "data/backups",
    "max_backups": 10,
    "scrape_auto_import": True,
    "scrape_skip_existing": True,
    "scrape_default_row_limit": 5000,
}


def load_settings(path: Optional[Path] = None) -> Dict[str, Any]:
    p = Path(path) if path else DEFAULT_SETTINGS_PATH
    settings = deepcopy(DEFAULTS)
    if p.is_file():
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for k, v in raw.items():
                    if k in DEFAULTS:
                        settings[k] = v
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    return normalize_settings(settings)


def save_settings(settings: Dict[str, Any], path: Optional[Path] = None) -> Path:
    p = Path(path) if path else DEFAULT_SETTINGS_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    clean = normalize_settings({**DEFAULTS, **(settings or {})})
    out = {k: clean[k] for k in DEFAULTS}
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return p


def normalize_settings(s: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(DEFAULTS)
    out.update({k: s[k] for k in DEFAULTS if k in s})
    out["db_path"] = str(out.get("db_path") or DEFAULTS["db_path"]).strip() or DEFAULTS["db_path"]
    out["backup_dir"] = (
        str(out.get("backup_dir") or DEFAULTS["backup_dir"]).strip() or DEFAULTS["backup_dir"]
    )
    out["backup_on_close"] = bool(out.get("backup_on_close", False))
    out["scrape_auto_import"] = bool(out.get("scrape_auto_import", True))
    out["scrape_skip_existing"] = bool(out.get("scrape_skip_existing", True))
    try:
        out["max_backups"] = max(0, min(int(out.get("max_backups", 10)), 500))
    except (TypeError, ValueError):
        out["max_backups"] = 10
    try:
        out["scrape_default_row_limit"] = max(0, int(out.get("scrape_default_row_limit", 5000)))
    except (TypeError, ValueError):
        out["scrape_default_row_limit"] = 5000
    return out
