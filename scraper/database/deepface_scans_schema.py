"""DeepFace scan table schema + photo fingerprint helper."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional


def photo_fingerprint(photo_path: Optional[str]) -> Optional[str]:
    raw = (photo_path or "").strip()
    if not raw:
        return None
    p = Path(raw)
    try:
        if not p.is_file():
            return None
        st = p.stat()
        try:
            resolved = str(p.resolve())
        except OSError:
            resolved = str(p)
        return f"{resolved}|{st.st_size}|{int(st.st_mtime)}"
    except OSError:
        return None


class DeepfaceScanSchemaMixin:
    """Ensure ``deepface_scans`` table exists with current columns."""

    def _ensure_deepface_scans_table(self, cursor: Optional[sqlite3.Cursor] = None) -> None:
        cur = cursor or self._conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS deepface_scans (
                arrest_id INTEGER PRIMARY KEY,
                photo_path TEXT,
                photo_fingerprint TEXT,
                scanned_at TEXT NOT NULL,
                top_label TEXT,
                top_confidence REAL,
                scores_json TEXT,
                backend TEXT,
                detector TEXT,
                face_detected INTEGER DEFAULT 1,
                error TEXT,
                is_hit INTEGER DEFAULT 0,
                recorded_race TEXT,
                predicted_label TEXT,
                severity TEXT,
                reason TEXT,
                scan_min_conf REAL,
                FOREIGN KEY (arrest_id) REFERENCES arrests(id) ON DELETE CASCADE
            )
            """
        )
        # Migrate legacy offender_id column name if someone copied SOR DB shape
        cols = {r[1] for r in cur.execute("PRAGMA table_info(deepface_scans)")}
        if "offender_id" in cols and "arrest_id" not in cols:
            # Leave legacy; create views via alias methods
            pass
        # Lightweight forward-migration: add any columns the current code needs
        # that an older DB may lack (guarded per-column so re-runs are no-ops).
        _wanted_cols = {
            "photo_path": "TEXT",
            "photo_fingerprint": "TEXT",
            "top_label": "TEXT",
            "top_confidence": "REAL",
            "scores_json": "TEXT",
            "backend": "TEXT",
            "detector": "TEXT",
            "face_detected": "INTEGER DEFAULT 1",
            "error": "TEXT",
            "is_hit": "INTEGER DEFAULT 0",
            "recorded_race": "TEXT",
            "predicted_label": "TEXT",
            "severity": "TEXT",
            "reason": "TEXT",
            "scan_min_conf": "REAL",
        }
        for _name, _decl in _wanted_cols.items():
            if _name not in cols:
                try:
                    cur.execute(
                        f"ALTER TABLE deepface_scans ADD COLUMN {_name} {_decl}"
                    )
                except sqlite3.OperationalError:
                    pass
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_deepface_scans_hit "
            "ON deepface_scans(is_hit) WHERE is_hit = 1"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_deepface_scans_scanned_at "
            "ON deepface_scans(scanned_at)"
        )
        if cursor is None:
            self._conn.commit()
