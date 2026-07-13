"""Persist DeepFace mugshot scan results (keyed by arrest_id)."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

from scraper.database.constants import _utc_now_iso


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


class DeepfaceScanMixin:
    """CRUD for ``deepface_scans`` table (one latest row per arrest)."""

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

    def get_deepface_scanned_ids(self, *, current_photo_only: bool = True) -> Set[int]:
        self._ensure_deepface_scans_table()
        rows = self._conn.execute(
            """
            SELECT s.arrest_id, s.photo_fingerprint, a.photo_path
            FROM deepface_scans s
            LEFT JOIN arrests a ON a.id = s.arrest_id
            """
        ).fetchall()
        out: Set[int] = set()
        for r in rows:
            try:
                aid = int(r[0])
            except (TypeError, ValueError):
                continue
            if not current_photo_only:
                out.add(aid)
                continue
            stored_fp = (r[1] or "").strip()
            cur_fp = photo_fingerprint(r[2] if len(r) > 2 else None)
            if stored_fp and cur_fp and stored_fp == cur_fp:
                out.add(aid)
            elif stored_fp and not cur_fp:
                out.add(aid)
            elif not stored_fp:
                out.add(aid)
        return out

    def count_deepface_scans(self) -> Dict[str, int]:
        self._ensure_deepface_scans_table()
        total = self._conn.execute("SELECT COUNT(*) FROM deepface_scans").fetchone()[0]
        hits = self._conn.execute(
            "SELECT COUNT(*) FROM deepface_scans WHERE is_hit = 1"
        ).fetchone()[0]
        return {"total": int(total or 0), "hits": int(hits or 0)}

    def upsert_deepface_scan(
        self,
        arrest_id: Optional[int] = None,
        *,
        offender_id: Optional[int] = None,  # SOR alias
        photo_path: Optional[str] = None,
        top_label: Optional[str] = None,
        top_confidence: float = 0.0,
        scores: Optional[Dict[str, float]] = None,
        backend: str = "",
        detector: str = "",
        face_detected: bool = True,
        error: Optional[str] = None,
        is_hit: bool = False,
        recorded_race: str = "",
        predicted_label: str = "",
        severity: str = "",
        reason: str = "",
        scan_min_conf: Optional[float] = None,
        scanned_at: Optional[str] = None,
    ) -> None:
        self._ensure_deepface_scans_table()
        aid = int(arrest_id if arrest_id is not None else offender_id or 0)
        fp = photo_fingerprint(photo_path)
        scores_json = json.dumps(scores or {}, ensure_ascii=False)
        self._conn.execute(
            """
            INSERT INTO deepface_scans (
                arrest_id, photo_path, photo_fingerprint, scanned_at,
                top_label, top_confidence, scores_json, backend, detector,
                face_detected, error, is_hit, recorded_race, predicted_label,
                severity, reason, scan_min_conf
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(arrest_id) DO UPDATE SET
                photo_path=excluded.photo_path,
                photo_fingerprint=excluded.photo_fingerprint,
                scanned_at=excluded.scanned_at,
                top_label=excluded.top_label,
                top_confidence=excluded.top_confidence,
                scores_json=excluded.scores_json,
                backend=excluded.backend,
                detector=excluded.detector,
                face_detected=excluded.face_detected,
                error=excluded.error,
                is_hit=excluded.is_hit,
                recorded_race=excluded.recorded_race,
                predicted_label=excluded.predicted_label,
                severity=excluded.severity,
                reason=excluded.reason,
                scan_min_conf=excluded.scan_min_conf
            """,
            (
                aid,
                (photo_path or "").strip() or None,
                fp,
                scanned_at or _utc_now_iso(),
                (top_label or "").strip() or None,
                float(top_confidence or 0.0),
                scores_json,
                (backend or "").strip() or None,
                (detector or "").strip() or None,
                1 if face_detected else 0,
                (error or None),
                1 if is_hit else 0,
                (recorded_race or "").strip() or None,
                (predicted_label or top_label or "").strip() or None,
                (severity or "").strip() or None,
                (reason or "").strip() or None,
                float(scan_min_conf) if scan_min_conf is not None else None,
            ),
        )
        self._conn.commit()

    def get_deepface_scan(self, arrest_id: int) -> Optional[Dict[str, Any]]:
        self._ensure_deepface_scans_table()
        row = self._conn.execute(
            "SELECT * FROM deepface_scans WHERE arrest_id = ?",
            (int(arrest_id),),
        ).fetchone()
        if not row:
            return None
        return self._deepface_scan_row_to_dict(row)

    def _list_deepface_scan_rows(
        self,
        *,
        limit: int = 0,
        min_confidence: float = 0.0,
        state: Optional[str] = None,
        source_system: Optional[str] = None,
        hits_only: bool = True,
        face_scored_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """Join stored scan rows with arrest records for Reports / Scan UI."""
        self._ensure_deepface_scans_table()
        sql = """
            SELECT s.arrest_id
            FROM deepface_scans s
            JOIN arrests a ON a.id = s.arrest_id
            WHERE COALESCE(s.top_confidence, 0) >= ?
        """
        params: list = [float(min_confidence or 0.0)]
        if hits_only:
            sql += " AND s.is_hit = 1"
        if face_scored_only:
            sql += (
                " AND COALESCE(s.face_detected, 1) = 1"
                " AND COALESCE(s.top_label, '') != ''"
                " AND LOWER(COALESCE(s.top_label, '')) NOT IN ('unknown', '')"
            )
        if state:
            sql += " AND UPPER(a.state) = UPPER(?)"
            params.append(state)
        if source_system:
            sql += " AND LOWER(COALESCE(a.source_system,'')) = LOWER(?)"
            params.append(source_system)
        sql += " ORDER BY s.top_confidence DESC, s.scanned_at DESC"
        if limit and int(limit) > 0:
            sql += " LIMIT ?"
            params.append(int(limit))
        ids = [int(r[0]) for r in self._conn.execute(sql, params).fetchall()]
        out: List[Dict[str, Any]] = []
        for aid in ids:
            scan = self.get_deepface_scan(aid)
            rec = self.get_arrest_by_id(aid)
            if not scan or not rec:
                continue
            rec = dict(rec)
            is_hit = bool(scan.get("is_hit"))
            rec["_deepface"] = {
                "top_label": scan.get("top_label"),
                "top_confidence": scan.get("top_confidence"),
                "scores": scan.get("scores") or {},
                "backend": scan.get("backend"),
                "detector": scan.get("detector"),
                "is_hit": is_hit,
                "severity": scan.get("severity"),
                "reason": scan.get("reason"),
                "scanned_at": scan.get("scanned_at"),
                "predicted_label": scan.get("predicted_label"),
                "recorded_race_scan": scan.get("recorded_race"),
            }
            rec["_deepface_is_hit"] = is_hit
            out.append(rec)
        return out

    def list_deepface_scored(
        self,
        *,
        limit: int = 0,
        min_confidence: float = 0.0,
        state: Optional[str] = None,
        source_system: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """All stored face scores (not only rows flagged ``is_hit`` at scan time)."""
        return self._list_deepface_scan_rows(
            limit=limit,
            min_confidence=min_confidence,
            state=state,
            source_system=source_system,
            hits_only=False,
            face_scored_only=True,
        )

    def list_deepface_hits(
        self,
        *,
        limit: int = 0,
        min_confidence: float = 0.0,
        state: Optional[str] = None,
        source_system: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        rows = self._list_deepface_scan_rows(
            limit=limit,
            min_confidence=min_confidence,
            state=state,
            source_system=source_system,
            hits_only=True,
        )
        for rec in rows:
            rec["_deepface_is_hit"] = True
        return rows

    def clear_deepface_scans(
        self,
        *,
        arrest_ids: Optional[Iterable[int]] = None,
        offender_ids: Optional[Iterable[int]] = None,
        hits_only: bool = False,
    ) -> int:
        self._ensure_deepface_scans_table()
        ids_src = arrest_ids if arrest_ids is not None else offender_ids
        if ids_src is not None:
            ids = [int(x) for x in ids_src]
            if not ids:
                return 0
            placeholders = ",".join("?" * len(ids))
            sql = f"DELETE FROM deepface_scans WHERE arrest_id IN ({placeholders})"
            if hits_only:
                sql += " AND is_hit = 1"
            cur = self._conn.execute(sql, ids)
        else:
            sql = "DELETE FROM deepface_scans"
            if hits_only:
                sql += " WHERE is_hit = 1"
            cur = self._conn.execute(sql)
        self._conn.commit()
        return int(cur.rowcount or 0)

    @staticmethod
    def _deepface_scan_row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        raw = d.get("scores_json") or "{}"
        try:
            scores = json.loads(raw) if isinstance(raw, str) else (raw or {})
        except (TypeError, json.JSONDecodeError):
            scores = {}
        d["scores"] = scores if isinstance(scores, dict) else {}
        d["is_hit"] = bool(d.get("is_hit"))
        d["face_detected"] = bool(d.get("face_detected", 1))
        # SOR UI often looks for offender_id
        if "arrest_id" in d and "offender_id" not in d:
            d["offender_id"] = d["arrest_id"]
        return d
