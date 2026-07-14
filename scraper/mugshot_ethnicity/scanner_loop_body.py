"""Body of scan_gross_misclassifications."""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence

from scraper.database import Database
from scraper.mugshot_ethnicity.labels import normalize_face_label
from scraper.mugshot_ethnicity.models import FaceEthnicityScore, GrossMisclassHit
from scraper.mugshot_ethnicity.scanner_candidates import collect_candidates, load_prior_hits
from scraper.mugshot_ethnicity.scanner_helpers import (
    _DEFAULT_RECORDED_TARGETS,
    is_hit,
    store_scan,
)
from scraper.mugshot_ethnicity.scorer import BackendUnavailableError, MugshotEthnicityScorer
from scraper.searcher import _canonical_race_key, format_race_label


def run_scan_loop(
    db=None, *, db_path=None, scorer=None, backend="auto",
    recorded_races=None, face_labels=None, min_confidence=0.85, limit=0,
    state=None, require_photo=True, progress=None, log=None, cancel=None,
    skip_scanned=True, force_rescan=False, persist=True, detector="",
    on_hit=None, on_photo=None, on_scored=None, source_system=None,
) -> List[GrossMisclassHit]:
    def _log(msg: str) -> None:
        if log:
            log(msg)

    def _cancelled() -> bool:
        if not cancel:
            return False
        try:
            return bool(cancel())
        except Exception:
            return False

    def _emit(hit: GrossMisclassHit) -> None:
        if on_hit:
            try:
                on_hit(hit)
            except Exception:
                pass

    own_db = False
    if db is None:
        db = Database(db_path or "data/arrests.db")
        own_db = True

    try:
        sc = scorer or MugshotEthnicityScorer(backend=backend)
    except BackendUnavailableError:
        if own_db:
            db.close()
        raise

    targets = {
        _canonical_race_key(r) for r in (recorded_races or list(_DEFAULT_RECORDED_TARGETS))
    }
    want_faces = {
        normalize_face_label(x) for x in (face_labels or ("black", "indian", "asian"))
    }
    want_faces.discard("unknown")

    already = set()
    if skip_scanned and not force_rescan:
        try:
            already = db.get_deepface_scanned_ids(current_photo_only=True)
        except Exception as e:
            _log(f"Could not load prior DeepFace scans (continuing): {e}")
            already = set()

    candidates, skipped, skipped_placeholder = collect_candidates(
        db, sc=sc, targets=targets, already=already, limit=limit, state=state,
        source_system=source_system, require_photo=require_photo, persist=persist,
        min_confidence=min_confidence, detector=detector,
    )
    _log(
        f"Mugshot gross-scan: {len(candidates)} to score"
        + (f", skipped {skipped} already scanned" if skipped else "")
        + (f", skipped {skipped_placeholder} placeholder silhouettes" if skipped_placeholder else "")
        + f" (recorded∈{sorted(targets)}, face∈{sorted(want_faces)}, "
        f"min_conf={min_confidence}, backend={sc.backend_name}"
        f"{', rescan' if force_rescan or not skip_scanned else ''})"
    )

    hits: List[GrossMisclassHit] = []
    if skip_scanned and not force_rescan and skipped:
        try:
            hits = load_prior_hits(
                db, targets=targets, want_faces=want_faces,
                min_confidence=min_confidence, limit=limit, state=state,
                source_system=source_system, emit=_emit,
            )
        except Exception as e:
            _log(f"Could not load prior DeepFace hits: {e}")

    total = len(candidates)
    scored = 0
    for i, rec in enumerate(candidates):
        if _cancelled():
            _log(
                f"Mugshot gross-scan cancelled after {i}/{total} new candidates "
                f"({len(hits)} hits total)"
            )
            break
        idx = i + 1
        if on_photo:
            try:
                on_photo(rec, idx, total)
            except Exception:
                pass
        if progress and (on_photo is not None or idx % 5 == 0 or idx == total or i == 0):
            try:
                progress(idx, total)
            except Exception:
                pass
        face = sc.score_record(rec)
        scored += 1
        race = (rec.get("race") or "").strip()
        race_disp = format_race_label(race) if race else race
        lab = normalize_face_label(face.top_label) if face.ok else "unknown"
        conf = float(face.top_confidence or 0.0) if face.ok else 0.0
        hit = bool(
            face.ok and is_hit(
                lab, conf, race, want_faces=want_faces, min_confidence=min_confidence
            )
        )
        severity = ""
        reason = ""
        if hit:
            severity = "high" if conf >= 0.9 else "medium"
            reason = (
                f"Face scores {lab} at {conf:.0%} but registry race is "
                f"{race_disp or race}"
            )
            gh = GrossMisclassHit(
                record=rec, recorded_race=race_disp or race, face=face,
                predicted_label=lab, confidence=conf, severity=severity, reason=reason,
            )
            hits.append(gh)
            _emit(gh)
            _log(
                f"  HIT id={rec.get('id')} "
                f"{rec.get('first_name')} {rec.get('last_name')} "
                f"race={race} face={lab}@{conf:.2f}"
            )
        if on_scored:
            try:
                on_scored(rec, face, hit, idx, total)
            except Exception:
                pass
        if persist:
            store_scan(
                db, rec, face, is_hit=hit, recorded_race=race_disp or race,
                predicted_label=lab if face.ok else "", severity=severity,
                reason=reason, min_confidence=min_confidence, detector=detector,
            )

    by_id: Dict[Any, GrossMisclassHit] = {}
    for h in hits:
        rid = (h.record or {}).get("id")
        key = rid if rid is not None else id(h)
        prev = by_id.get(key)
        if prev is None or h.confidence > prev.confidence:
            by_id[key] = h
    hits = list(by_id.values())
    hits.sort(key=lambda h: (-h.confidence, h.predicted_label))
    _log(
        f"Mugshot gross-scan done: {len(hits)} hits "
        f"({scored} newly scored, {skipped} skipped already scanned)"
    )
    if own_db:
        db.close()
    return hits
