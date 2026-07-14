"""DeepFace local race attribute backend."""
from __future__ import annotations

from typing import Dict, List, Optional

from scraper.mugshot_ethnicity.backends_base import EthnicityBackend
from scraper.mugshot_ethnicity.labels import normalize_face_label
from scraper.mugshot_ethnicity.models import FaceEthnicityScore


class DeepFaceBackend(EthnicityBackend):
    """
    Local DeepFace race attribute model.

    Install::

        pip install -r requirements-vision.txt
        # or: pip install deepface tensorflow

    First ``analyze()`` downloads weights into ``~/.deepface/weights/`` (offline
    afterward). Detector default ``retinaface`` is accurate for mugshots;
    falls back to ``opencv`` if retinaface weights fail.
    """

    name = "deepface"
    is_production = True

    def __init__(
        self,
        detector_backend: Optional[str] = None,
        *,
        enforce_detection: bool = False,
    ):
        # enforce_detection=False: still score when face box is weak (common on
        # low-res registry thumbs); confidence will reflect model uncertainty.
        det = (detector_backend or "").strip()
        if not det:
            try:
                from scraper.app_settings import load_settings

                det = str(load_settings().get("deepface_detector") or "retinaface")
            except Exception:
                det = "retinaface"
        self.detector_backend = det or "retinaface"
        self.enforce_detection = bool(enforce_detection)
        self._detectors_tried: List[str] = []

    def is_available(self) -> bool:
        try:
            import deepface  # noqa: F401
            return True
        except Exception:
            return False

    def analyze(self, photo_path: str) -> FaceEthnicityScore:
        try:
            # Before any TF/keras import — required for RetinaFace on TF 2.16+
            from scraper.mugshot_ethnicity.setup import configure_tf_keras_env

            configure_tf_keras_env()
            from deepface import DeepFace
        except Exception as e:
            return FaceEthnicityScore(
                photo_path=photo_path,
                top_label="unknown",
                top_confidence=0.0,
                backend=self.name,
                face_detected=False,
                error=f"deepface import failed: {e}",
            )

        detectors = [self.detector_backend]
        # Prefer SSD/YuNet over broken OpenCV Haar (headless wheels lack cascades)
        for alt in ("retinaface", "ssd", "yunet", "opencv", "mtcnn"):
            if alt not in detectors:
                detectors.append(alt)

        last_err: Optional[str] = None
        for det in detectors:
            try:
                results = DeepFace.analyze(
                    img_path=str(photo_path),
                    actions=["race"],
                    detector_backend=det,
                    enforce_detection=self.enforce_detection,
                    silent=True,
                )
                if isinstance(results, list):
                    result = results[0] if results else {}
                else:
                    result = results or {}
                race_scores = result.get("race") or {}
                if not isinstance(race_scores, dict) or not race_scores:
                    last_err = "empty race scores"
                    continue

                scores: Dict[str, float] = {}
                for k, v in race_scores.items():
                    lab = normalize_face_label(str(k))
                    try:
                        val = float(v)
                    except (TypeError, ValueError):
                        continue
                    # DeepFace returns 0–100 percentages
                    if val > 1.5:
                        val = val / 100.0
                    scores[lab] = max(scores.get(lab, 0.0), val)
                if not scores:
                    last_err = "unparseable race scores"
                    continue
                total = sum(scores.values()) or 1.0
                scores = {k: v / total for k, v in scores.items()}
                top = max(scores, key=scores.get)
                self._detectors_tried.append(det)
                return FaceEthnicityScore(
                    photo_path=photo_path,
                    top_label=top,
                    top_confidence=float(scores[top]),
                    scores=scores,
                    backend=f"{self.name}:{det}",
                    face_detected=True,
                    raw={
                        "dominant_race": result.get("dominant_race"),
                        "race": race_scores,
                        "detector": det,
                        "region": result.get("region"),
                    },
                )
            except Exception as e:
                last_err = str(e)
                continue

        return FaceEthnicityScore(
            photo_path=photo_path,
            top_label="unknown",
            top_confidence=0.0,
            backend=self.name,
            face_detected=False,
            error=last_err or "deepface analyze failed",
        )
