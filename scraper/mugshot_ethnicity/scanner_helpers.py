"""Scanner helpers: race targets, hit rules, persist scores."""
from __future__ import annotations

from typing import Any, Dict, Set

from scraper.database import Database
from scraper.mugshot_ethnicity.labels import (
    face_contradicts_recorded,
    is_gross_face_vs_white,
    normalize_face_label,
)
from scraper.mugshot_ethnicity.models import FaceEthnicityScore
from scraper.searcher import Misclassification, _canonical_race_key, format_race_label

_DEFAULT_RECORDED_TARGETS = frozenset({"WHITE"})


def race_is_target(recorded_race: str, targets: Set[str]) -> bool:
    """True if *recorded_race* matches any selected scan target (canonical keys)."""
    if not targets:
        return False
    key = _canonical_race_key(recorded_race or "")
    if key in targets:
        return True
    raw = (recorded_race or "").upper()
    if "WHITE" in targets and (
        "WHITE" in raw or raw.strip() in ("W",) or "[W]" in raw.replace(" ", "")
    ):
        if "BLACK" in raw or "ASIAN" in raw or "INDIAN" in raw:
            if key not in targets:
                return False
        else:
            return True
    if "BLACK" in targets and ("BLACK" in raw or raw.strip() in ("B",)):
        return True
    if "ASIAN" in targets and "ASIAN" in raw:
        return True
    if "HISPANIC" in targets and ("HISPANIC" in raw or "LATINO" in raw):
        return True
    if "INDIAN" in targets and "INDIAN" in raw:
        return True
    if "OTHER" in targets and key in ("OTHER", "UNKNOWN", ""):
        return True
    return False


def is_hit(
    lab: str,
    conf: float,
    race: str,
    *,
    want_faces: Set[str],
    min_confidence: float,
) -> bool:
    if conf < float(min_confidence):
        return False
    if lab not in want_faces:
        return False
    if face_contradicts_recorded(lab, race):
        return True
    if _canonical_race_key(race) == "WHITE" and is_gross_face_vs_white(lab):
        return True
    return False


def store_scan(
    db: Database,
    rec: Dict[str, Any],
    face: FaceEthnicityScore,
    *,
    is_hit: bool,
    recorded_race: str,
    predicted_label: str,
    severity: str,
    reason: str,
    min_confidence: float,
    detector: str = "",
) -> None:
    oid = rec.get("id")
    if oid is None:
        return
    try:
        oid_i = int(oid)
    except (TypeError, ValueError):
        return
    try:
        db.upsert_deepface_scan(
            oid_i,
            photo_path=face.photo_path or rec.get("photo_path"),
            top_label=face.top_label,
            top_confidence=float(face.top_confidence or 0.0),
            scores=dict(face.scores or {}),
            backend=face.backend or "",
            detector=detector,
            face_detected=bool(face.face_detected),
            error=face.error,
            is_hit=is_hit,
            recorded_race=recorded_race,
            predicted_label=predicted_label,
            severity=severity,
            reason=reason,
            scan_min_conf=float(min_confidence),
        )
    except Exception:
        pass


def deepface_hit_to_misclassification(rec: Dict[str, Any]) -> Misclassification:
    """Convert a DB offender row with ``_deepface`` payload into a Reports row."""
    df = rec.get("_deepface") or {}
    race = (
        format_race_label(rec.get("race") or "")
        or (df.get("recorded_race_scan") or rec.get("race") or "—")
    )
    lab = normalize_face_label(df.get("predicted_label") or df.get("top_label") or "")
    conf = float(df.get("top_confidence") or 0.0)
    eth = (lab or "unknown").replace("_", " ").title()
    if eth.lower() == "indian":
        eth = "Indian (South Asian)"
    names = ["deepface"]
    if lab:
        names.append(f"face:{lab}@{conf:.2f}")
    if df.get("severity"):
        names.append(f"severity:{df.get('severity')}")
    if df.get("reason"):
        names.append(str(df.get("reason"))[:80])
    out_rec = dict(rec)
    out_rec["_deepface"] = df
    out_rec["_deepface_is_hit"] = True
    out_rec["_source"] = "deepface"
    return Misclassification(
        record=out_rec,
        expected_race=str(race),
        likely_ethnicity=eth,
        confidence=conf,
        matching_names=names,
    )
