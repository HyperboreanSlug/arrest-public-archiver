"""Base + mock ethnicity backends."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional

from scraper.mugshot_ethnicity.labels import normalize_face_label
from scraper.mugshot_ethnicity.models import FACE_LABELS, FaceEthnicityScore


class EthnicityBackend(ABC):
    """Score a face image → ethnicity distribution (local models only)."""

    name: str = "base"
    # True for real vision stacks; False for test doubles
    is_production: bool = True

    @abstractmethod
    def is_available(self) -> bool:
        ...

    @abstractmethod
    def analyze(self, photo_path: str) -> FaceEthnicityScore:
        ...


class MockBackend(EthnicityBackend):
    """Deterministic backend for tests (path stem encodes label__conf)."""

    name = "mock"
    is_production = False

    def __init__(self, fixed: Optional[Dict[str, float]] = None):
        self.fixed = fixed

    def is_available(self) -> bool:
        return True

    def analyze(self, photo_path: str) -> FaceEthnicityScore:
        if self.fixed:
            scores = {k: float(v) for k, v in self.fixed.items()}
            top = max(scores, key=scores.get)
            return FaceEthnicityScore(
                photo_path=photo_path,
                top_label=top,
                top_confidence=float(scores[top]),
                scores=scores,
                backend=self.name,
                face_detected=True,
            )
        stem = Path(photo_path).stem.lower()
        label = "unknown"
        conf = 0.9
        if "__" in stem:
            lab, conf_s = stem.rsplit("__", 1)
            label = normalize_face_label(lab)
            try:
                conf = float(conf_s.replace("_", "."))
            except ValueError:
                conf = 0.9
        else:
            for cand in FACE_LABELS:
                if cand in stem.replace("-", "_"):
                    label = cand
                    break
        scores = {
            lab: (conf if lab == label else (1.0 - conf) / max(1, len(FACE_LABELS) - 1))
            for lab in FACE_LABELS
            if lab != "unknown"
        }
        if label == "unknown":
            scores = {"unknown": 1.0}
        return FaceEthnicityScore(
            photo_path=photo_path,
            top_label=label,
            top_confidence=conf if label != "unknown" else 0.0,
            scores=scores,
            backend=self.name,
            face_detected=label != "unknown",
        )
