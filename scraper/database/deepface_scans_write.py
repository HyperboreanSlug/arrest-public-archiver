"""DeepFace scan upsert / clear / row conversion."""
from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, Iterable, Optional

from scraper.database.constants import _utc_now_iso
from scraper.database.deepface_scans_schema import photo_fingerprint


class DeepfaceScanWriteMixin:
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
