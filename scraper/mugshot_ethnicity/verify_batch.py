"""Batch mugshot verification over misclassification lists."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from scraper.ethnic_names import EthnicNameDatabase, get_ethnic_database
from scraper.mugshot_ethnicity.models import VerifyResult
from scraper.mugshot_ethnicity.scorer import BackendUnavailableError, MugshotEthnicityScorer
from scraper.mugshot_ethnicity.verify_record import verify_record
from scraper.searcher import Misclassification


def verify_misclassifications(
    items: Sequence[Union[Misclassification, Dict[str, Any]]],
    *,
    scorer: Optional[MugshotEthnicityScorer] = None,
    ethnic_db: Optional[EthnicNameDatabase] = None,
    face_min_conf: float = 0.75,
    name_min_conf: float = 0.5,
    combined_min_conf: float = 0.8,
    backend: str = "auto",
    only_with_photo: bool = True,
    progress: Optional[Any] = None,
) -> List[VerifyResult]:
    """
    Run mugshot verify on a list of misclassification hits or raw records.

    Designed to sit on top of ``SexOffenderSearcher.analyze_ethnicities``.
    """
    try:
        sc = scorer or MugshotEthnicityScorer(backend=backend)
    except BackendUnavailableError:
        raise

    eth_db = ethnic_db or get_ethnic_database()
    out: List[VerifyResult] = []
    n = len(items)
    for i, item in enumerate(items):
        if isinstance(item, Misclassification):
            rec = dict(item.record or {})
            ne = item.likely_ethnicity
            nc = float(item.confidence or 0.0)
        else:
            rec = dict(item or {})
            ne = None
            nc = None
        if only_with_photo:
            p = (rec.get("photo_path") or "").strip()
            if not p or not Path(p).is_file():
                continue
        result = verify_record(
            rec,
            scorer=sc,
            ethnic_db=eth_db,
            name_ethnicity=ne,
            name_confidence=nc,
            face_min_conf=face_min_conf,
            name_min_conf=name_min_conf,
            combined_min_conf=combined_min_conf,
        )
        out.append(result)
        if progress and (i + 1) % 25 == 0:
            try:
                progress(i + 1, n)
            except Exception:
                pass
    # Prefer confirmed misclass first
    out.sort(
        key=lambda r: (
            0 if r.confirms_misclass else 1,
            0 if r.verdict == "disagree" else 1,
            -r.combined_confidence,
        )
    )
    return out
