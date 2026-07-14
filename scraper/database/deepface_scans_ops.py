"""DeepFace scan list / count / get helpers."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from scraper.database.deepface_scans_schema import photo_fingerprint


class DeepfaceScanOpsMixin:
    """Read / list helpers for ``deepface_scans``."""

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
