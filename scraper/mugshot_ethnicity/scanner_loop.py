"""Gross face-vs-recorded-race scan loop."""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence, Set

from scraper.database import Database
from scraper.mugshot_ethnicity.labels import normalize_face_label
from scraper.mugshot_ethnicity.models import FaceEthnicityScore, GrossMisclassHit
from scraper.mugshot_ethnicity.photo_quality import (
    is_placeholder_photo,
    placeholder_reason,
    resolve_photo_path,
)
from scraper.mugshot_ethnicity.scanner_helpers import (
    _DEFAULT_RECORDED_TARGETS,
    is_hit,
    race_is_target,
    store_scan,
)
from scraper.mugshot_ethnicity.scorer import BackendUnavailableError, MugshotEthnicityScorer
from scraper.searcher import _canonical_race_key, format_race_label


def scan_gross_misclassifications(
    db: Optional[Database] = None,
    *,
    db_path: Optional[str] = None,
    scorer: Optional[MugshotEthnicityScorer] = None,
    backend: str = "auto",
    recorded_races: Optional[Sequence[str]] = None,
    face_labels: Optional[Sequence[str]] = None,
    min_confidence: float = 0.85,
    limit: int = 0,
    state: Optional[str] = None,
    require_photo: bool = True,
    progress: Optional[Callable[[int, int], None]] = None,
    log: Optional[Callable[[str], None]] = None,
    cancel: Optional[Callable[[], bool]] = None,
    skip_scanned: bool = True,
    force_rescan: bool = False,
    persist: bool = True,
    detector: str = "",
    on_hit: Optional[Callable[[GrossMisclassHit], None]] = None,
    on_photo: Optional[Callable[[Dict[str, Any], int, int], None]] = None,
    on_scored: Optional[
        Callable[[Dict[str, Any], FaceEthnicityScore, bool, int, int], None]
    ] = None,
    source_system: Optional[str] = None,
) -> List[GrossMisclassHit]:
    """Scan mugshots for high-confidence face ethnicity vs recorded race."""
    from scraper.mugshot_ethnicity.scanner_loop_body import run_scan_loop

    return run_scan_loop(
        db=db,
        db_path=db_path,
        scorer=scorer,
        backend=backend,
        recorded_races=recorded_races,
        face_labels=face_labels,
        min_confidence=min_confidence,
        limit=limit,
        state=state,
        require_photo=require_photo,
        progress=progress,
        log=log,
        cancel=cancel,
        skip_scanned=skip_scanned,
        force_rescan=force_rescan,
        persist=persist,
        detector=detector,
        on_hit=on_hit,
        on_photo=on_photo,
        on_scored=on_scored,
        source_system=source_system,
    )
