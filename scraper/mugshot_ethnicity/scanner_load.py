"""Load stored DeepFace hits as Misclassification rows."""
from __future__ import annotations

from typing import List, Optional, Sequence, Set

from scraper.database import Database
from scraper.mugshot_ethnicity.labels import normalize_face_label
from scraper.mugshot_ethnicity.photo_quality import is_placeholder_photo
from scraper.mugshot_ethnicity.scanner_helpers import (
    deepface_hit_to_misclassification,
    is_hit,
    race_is_target,
)
from scraper.searcher import Misclassification, _canonical_race_key


def load_deepface_hits_as_misclass(
    db: Optional[Database] = None,
    *,
    db_path: Optional[str] = None,
    min_confidence: float = 0.0,
    state: Optional[str] = None,
    limit: int = 0,
    recorded_races: Optional[Sequence[str]] = None,
    face_labels: Optional[Sequence[str]] = None,
    source_system: Optional[str] = None,
    revalidate: bool = True,
) -> List[Misclassification]:
    """Load stored DeepFace hits for Reports / Browse → DeepFace."""
    own = False
    if db is None:
        db = Database(db_path or "data/arrests.db")
        own = True
    try:
        if recorded_races is None or face_labels is None:
            try:
                from scraper.app_settings import load_settings

                sett = load_settings()
            except Exception:
                sett = {}
            if recorded_races is None:
                raw_r = str(sett.get("deepface_scan_recorded") or "WHITE")
                recorded_races = [
                    p.strip().upper()
                    for p in raw_r.replace(";", ",").split(",")
                    if p.strip()
                ] or ["WHITE"]
            if face_labels is None:
                raw_f = str(
                    sett.get("deepface_scan_faces") or "black,indian,asian"
                )
                face_labels = [
                    p.strip().lower()
                    for p in raw_f.replace(";", ",").split(",")
                    if p.strip()
                ] or ["black", "indian", "asian"]

        targets: Set[str] = {
            _canonical_race_key(r) or str(r).strip().upper()
            for r in (recorded_races or [])
            if str(r).strip()
        }
        want_faces: Set[str] = {
            normalize_face_label(f) for f in (face_labels or []) if str(f).strip()
        }
        want_faces.discard("")
        want_faces.discard("unknown")

        loader = db.list_deepface_scored if revalidate else db.list_deepface_hits
        rows = loader(
            limit=limit,
            min_confidence=(0.0 if revalidate else min_confidence),
            state=state,
            source_system=source_system,
        )
        out: List[Misclassification] = []
        for r in rows:
            photo = (r.get("photo_path") or "").strip()
            if photo and is_placeholder_photo(photo):
                continue
            if revalidate:
                df = r.get("_deepface") or {}
                lab = normalize_face_label(
                    df.get("predicted_label") or df.get("top_label") or ""
                )
                conf = float(df.get("top_confidence") or 0.0)
                race = (r.get("race") or "").strip()
                if targets and not race_is_target(race, targets):
                    continue
                if want_faces and not is_hit(
                    lab,
                    conf,
                    race,
                    want_faces=want_faces,
                    min_confidence=float(min_confidence or 0.0),
                ):
                    continue
            out.append(deepface_hit_to_misclassification(r))
        return out
    finally:
        if own:
            db.close()
