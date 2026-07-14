"""Static DeepFace weight / detector catalog data."""
from __future__ import annotations

from typing import Any, Dict, List

from scraper.mugshot_ethnicity.weights_models import WEIGHT_MODELS

# Filenames DeepFace stores under ~/.deepface/weights/ (see deepface sources).
# Empty list = built-in / no cache file required.
WEIGHT_CACHE_FILES: Dict[str, List[str]] = {
    "Race": ["race_model_single_batch.h5"],
    "Age": ["age_model_weights.h5"],
    "Gender": ["gender_model_weights.h5"],
    "Emotion": ["facial_expression_model_weights.h5"],
    "VGG-Face": ["vgg_face_weights.h5"],
    "Facenet": ["facenet_weights.h5"],
    "Facenet512": ["facenet512_weights.h5"],
    "ArcFace": ["arcface_weights.h5"],
    "OpenFace": ["openface_weights.h5"],
    "SFace": ["face_recognition_sface_2021dec.onnx"],
}

DETECTOR_CACHE_FILES: Dict[str, List[str]] = {
    "retinaface": ["retinaface.h5"],
    "opencv": [],  # Haar cascades ship with OpenCV
    "ssd": [
        "deploy.prototxt",
        "res10_300x300_ssd_iter_140000.caffemodel",
    ],
    "mtcnn": [],  # weights live inside the mtcnn package, not ~/.deepface
    "yunet": ["face_detection_yunet_2023mar.onnx"],
}

# Incomplete downloads are often tiny stubs
_MIN_BYTES = 8_000

# Approximate VRAM when the model is loaded on GPU (TensorFlow/CUDA).
# CPU-only runs use system RAM instead (often 1.5–3× the weight file size).
# ``vram_short`` is shown in dropdowns / compact UI; ``vram`` is full detail.
DETECTOR_OPTIONS: List[Dict[str, Any]] = [
    {
        "id": "retinaface",
        "label": "RetinaFace (recommended)",
        "size": "~100 MB disk",
        "vram_short": "~0.5–1.0 GB VRAM",
        "vram": "~0.5–1.0 GB GPU (or ~1–2 GB RAM on CPU)",
        "speed": "Medium",
        "summary": "Best face boxes for mugshots and low-quality registry photos.",
        "detail": (
            "Neural face detector. Locates the face crop before Race runs. "
            "Misses fewer faces on angled/compressed mugshots than Haar. "
            "Slightly slower than OpenCV; worth it for batch accuracy. "
            "Only one detector is active at a time — pick this OR another, not both."
        ),
    },
    {
        "id": "opencv",
        "label": "OpenCV Haar (fast / no download)",
        "size": "Built-in (no extra file)",
        "vram_short": "~0 GB VRAM",
        "vram": "~0 GB dedicated (CPU; negligible GPU)",
        "speed": "Fastest",
        "summary": "Classic cascade detector; no weight download.",
        "detail": (
            "CPU Haar cascade shipped with OpenCV — no detector file to download. "
            "Lowest memory cost. Can miss rotated faces, tight crops, or heavy "
            "compression. Use if GPU/disk is tight or you only need a quick smoke test."
        ),
    },
    {
        "id": "ssd",
        "label": "SSD (OpenCV DNN)",
        "size": "~10 MB disk",
        "vram_short": "~0.2–0.4 GB VRAM",
        "vram": "~0.2–0.4 GB GPU (or ~0.5 GB RAM on CPU)",
        "speed": "Fast",
        "summary": "Small neural detector; better than Haar, lighter than RetinaFace.",
        "detail": (
            "OpenCV DNN SSD face detector. Middle ground: better boxes than Haar, "
            "less VRAM and disk than RetinaFace. Fine for mostly frontal photos."
        ),
    },
    {
        "id": "mtcnn",
        "label": "MTCNN",
        "size": "~2 MB disk",
        "vram_short": "~0.3–0.6 GB VRAM",
        "vram": "~0.3–0.6 GB GPU (or ~1 GB RAM on CPU)",
        "speed": "Medium–slow",
        "summary": "Multi-stage CNN; handles pose variation better than Haar.",
        "detail": (
            "Three cascaded networks (propose → refine → landmarks). More robust "
            "to pose than Haar; slower on CPU. Moderate VRAM if GPU-accelerated."
        ),
    },
    {
        "id": "yunet",
        "label": "YuNet",
        "size": "~1 MB disk",
        "vram_short": "~0.1–0.3 GB VRAM",
        "vram": "~0.1–0.3 GB GPU (or ~0.3 GB RAM on CPU)",
        "speed": "Fast",
        "summary": "Tiny modern detector (OpenCV zoo).",
        "detail": (
            "Very small OpenCV zoo model. Low disk and VRAM. Prefer when resources "
            "are limited and photos are mostly frontal."
        ),
    },
]

DOWNLOAD_GUIDANCE = (
    "Download guidance — one vs many:\n"
    "• Race tools need ONE weight: “Race / ethnicity” (checked by default).\n"
    "• Plus ONE face detector (dropdown above). Detectors are alternatives, not a set to collect.\n"
    "• Do NOT multi-select Age/Gender/Emotion for better race scores — they are unrelated nets.\n"
    "• Do NOT multi-select recognition models (VGG-Face, ArcFace, FaceNet…). Those are for "
    "“same person?” only; if you ever need that, pick a single recognition model.\n"
    "• Extra downloads only cost disk now; VRAM rises when a model is actually loaded."
)

# Re-export for importers that expect WEIGHT_MODELS on weights_data
__all__ = [
    "WEIGHT_CACHE_FILES",
    "DETECTOR_CACHE_FILES",
    "DETECTOR_OPTIONS",
    "WEIGHT_MODELS",
    "DOWNLOAD_GUIDANCE",
    "_MIN_BYTES",
]
