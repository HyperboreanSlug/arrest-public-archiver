"""Collect and filter mugshot scan candidates."""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from scraper.database import Database
from scraper.mugshot_ethnicity.labels import normalize_face_label
from scraper.mugshot_ethnicity.models import FaceEthnicityScore
from scraper.mugshot_ethnicity.photo_quality import (
    is_placeholder_photo,
    placeholder_reason,
    resolve_photo_path,
)
from scraper.mugshot_ethnicity.scanner_helpers import race_is_target, store_scan
from scraper.searcher import format_race_label


def collect_candidates(
    db: Database,
    *,
    sc,
    targets: Set[str],
    already: Set[int],
    limit: int,
    state: Optional[str],
    source_system: Optional[str],
    require_photo: bool,
    persist: bool,
    min_confidence: float,
    detector: str,
) -> Tuple[List[Dict[str, Any]], int, int]:
    sql = (
        "SELECT * FROM arrests "
        "WHERE photo_path IS NOT NULL AND TRIM(photo_path) != '' "
        "AND race IS NOT NULL AND TRIM(race) != ''"
    )
    params: list = []
    if state:
        sql += " AND UPPER(state) = UPPER(?)"
        params.append(state)
    if source_system and str(source_system).strip().lower() not in ("", "all", "*"):
        sql += " AND LOWER(COALESCE(source_system,'')) = LOWER(?)"
        params.append(str(source_system).strip())
    sql += " ORDER BY id ASC"
    if limit and int(limit) > 0:
        sql += " LIMIT ?"
        params.append(int(limit) * 8 if int(limit) < 50000 else int(limit))

    rows = [dict(r) for r in db._conn.execute(sql, params).fetchall()]
    candidates = []
    skipped = 0
    skipped_placeholder = 0
    for rec in rows:
        race = (rec.get("race") or "").strip()
        if not race_is_target(race, targets):
            continue
        photo = (rec.get("photo_path") or "").strip()
        if require_photo:
            resolved = resolve_photo_path(photo) if photo else None
            if not photo or resolved is None:
                continue
            photo = str(resolved)
            rec = dict(rec)
            rec["photo_path"] = photo
        try:
            oid = int(rec["id"]) if rec.get("id") is not None else None
        except (TypeError, ValueError):
            oid = None
        if photo and is_placeholder_photo(photo):
            skipped_placeholder += 1
            if persist and oid is not None:
                try:
                    reason_stub = placeholder_reason(photo) or "placeholder"
                    face_stub = FaceEthnicityScore(
                        photo_path=photo,
                        top_label="unknown",
                        top_confidence=0.0,
                        backend=sc.backend_name,
                        face_detected=False,
                        error=reason_stub,
                    )
                    store_scan(
                        db, rec, face_stub, is_hit=False,
                        recorded_race=format_race_label(race) if race else race,
                        predicted_label="", severity="", reason="",
                        min_confidence=min_confidence, detector=detector,
                    )
                except Exception:
                    pass
            continue
        if oid is not None and oid in already:
            skipped += 1
            continue
        candidates.append(rec)
        if limit and int(limit) > 0 and len(candidates) >= int(limit):
            break
    return candidates, skipped, skipped_placeholder


def load_prior_hits(
    db: Database,
    *,
    targets: Set[str],
    want_faces: Set[str],
    min_confidence: float,
    limit: int,
    state: Optional[str],
    source_system: Optional[str],
    emit: Callable,
) -> List:
    from scraper.mugshot_ethnicity.models import GrossMisclassHit
    from scraper.mugshot_ethnicity.scanner_helpers import is_hit

    hits = []
    try:
        for rec in db.list_deepface_scored(
            min_confidence=0.0, state=state, source_system=source_system,
        ):
            if limit and int(limit) > 0 and len(hits) >= int(limit) * 2:
                break
            df = rec.get("_deepface") or {}
            lab = normalize_face_label(
                df.get("predicted_label") or df.get("top_label") or ""
            )
            conf = float(df.get("top_confidence") or 0.0)
            race = (rec.get("race") or "").strip()
            if not race_is_target(race, targets):
                continue
            if not is_hit(
                lab, conf, race, want_faces=want_faces, min_confidence=min_confidence
            ):
                continue
            prior_photo = (rec.get("photo_path") or "").strip()
            if prior_photo and is_placeholder_photo(prior_photo):
                continue
            face = FaceEthnicityScore(
                photo_path=prior_photo, top_label=lab, top_confidence=conf,
                scores=dict(df.get("scores") or {}),
                backend=str(df.get("backend") or "deepface"), face_detected=True,
            )
            gh = GrossMisclassHit(
                record=rec,
                recorded_race=format_race_label(race) if race else race,
                face=face, predicted_label=lab, confidence=conf,
                severity=str(df.get("severity") or ("high" if conf >= 0.9 else "medium")),
                reason=str(df.get("reason") or ""),
            )
            hits.append(gh)
            emit(gh)
    except Exception:
        pass
    return hits
