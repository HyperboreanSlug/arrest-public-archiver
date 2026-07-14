"""DeepFace attribute + recognition model option definitions."""
from __future__ import annotations

from typing import Any, Dict, List

# Attribute + recognition models DeepFace.build_model can fetch.
WEIGHT_MODELS: List[Dict[str, Any]] = [
    {
        "id": "Race",
        "label": "Race / ethnicity (required)",
        "size": "~500 MB disk",
        "vram_short": "~1.0–1.5 GB VRAM",
        "vram": "~1.0–1.5 GB GPU when loaded (or ~2–3 GB RAM on CPU)",
        "category": "attribute",
        "required": True,
        "summary": "Only model required for mugshot race / ethnicity scoring.",
        "detail": (
            "Softmax over White, Black, Asian, Indian, Middle Eastern, Latino Hispanic. "
            "This is the sole attribute net mugshot-verify / mugshot-scan load for race. "
            "Downloading Age, Gender, Emotion, or any recognition model does not change "
            "these probabilities — they are different networks with different heads."
        ),
    },
    {
        "id": "Age",
        "label": "Age (optional — not for race)",
        "size": "~500 MB disk",
        "vram_short": "~1.0–1.5 GB VRAM",
        "vram": "~1.0–1.5 GB GPU if loaded",
        "category": "attribute",
        "required": False,
        "summary": "Separate network that estimates apparent age only.",
        "detail": (
            "Independent VGG-Face-based age head. Shares no training objective with "
            "Race. Skip for misclass tools; only download if you will analyze age."
        ),
    },
    {
        "id": "Gender",
        "label": "Gender (optional — not for race)",
        "size": "~500 MB disk",
        "vram_short": "~1.0–1.5 GB VRAM",
        "vram": "~1.0–1.5 GB GPU if loaded",
        "category": "attribute",
        "required": False,
        "summary": "Separate network for apparent gender only.",
        "detail": (
            "Independent gender classifier. Not used by the race mismatch pipeline. "
            "Same disk/VRAM cost class as Race if loaded — skip unless needed."
        ),
    },
    {
        "id": "Emotion",
        "label": "Emotion (optional — not for race)",
        "size": "~50 MB disk",
        "vram_short": "~0.3–0.5 GB VRAM",
        "vram": "~0.3–0.5 GB GPU if loaded",
        "category": "attribute",
        "required": False,
        "summary": "Expression classes (happy, sad, angry, …).",
        "detail": (
            "Smaller attribute net for facial expression. Unused by race tools. "
            "Safe to leave unchecked."
        ),
    },
    {
        "id": "VGG-Face",
        "label": "VGG-Face identity (optional)",
        "size": "~500 MB disk",
        "vram_short": "~1.0–1.5 GB VRAM",
        "vram": "~1.0–1.5 GB GPU if loaded",
        "category": "recognition",
        "required": False,
        "summary": "Identity embeddings (“same person?”) — not race labels.",
        "detail": (
            "Produces a face embedding for identity comparison (verify/find). "
            "Cannot output ethnicity. Large classic model. Skip for race tools; "
            "if you need identity later, prefer ArcFace or FaceNet512 instead of "
            "downloading several recognition models."
        ),
    },
    {
        "id": "Facenet",
        "label": "FaceNet 128d identity (optional)",
        "size": "~90 MB disk",
        "vram_short": "~0.5–0.8 GB VRAM",
        "vram": "~0.5–0.8 GB GPU if loaded",
        "category": "recognition",
        "required": False,
        "summary": "Google FaceNet 128-D identity embeddings.",
        "detail": (
            "Smaller identity embedding (128 dims). Not used for race. "
            "If you pick FaceNet, prefer Facenet512 over this — do not need both."
        ),
    },
    {
        "id": "Facenet512",
        "label": "FaceNet 512d identity (optional)",
        "size": "~90 MB disk",
        "vram_short": "~0.6–1.0 GB VRAM",
        "vram": "~0.6–1.0 GB GPU if loaded",
        "category": "recognition",
        "required": False,
        "summary": "FaceNet 512-D (richer identity vector than 128d).",
        "detail": (
            "Higher-dimension FaceNet embedding. Alternative to VGG-Face/ArcFace for "
            "same-person match. Download at most one recognition model."
        ),
    },
    {
        "id": "ArcFace",
        "label": "ArcFace identity (optional)",
        "size": "~130 MB disk",
        "vram_short": "~0.6–1.0 GB VRAM",
        "vram": "~0.6–1.0 GB GPU if loaded",
        "category": "recognition",
        "required": False,
        "summary": "Strong modern identity model; alternative to VGG-Face/FaceNet.",
        "detail": (
            "Often best same-person accuracy among DeepFace options. Mutually "
            "alternative to VGG-Face/FaceNet — pick one recognition stack, not all. "
            "Still unused by race scoring."
        ),
    },
    {
        "id": "OpenFace",
        "label": "OpenFace identity (optional)",
        "size": "~15 MB disk",
        "vram_short": "~0.2–0.4 GB VRAM",
        "vram": "~0.2–0.4 GB GPU if loaded",
        "category": "recognition",
        "required": False,
        "summary": "Lightweight identity embeddings.",
        "detail": (
            "Smallest recognition option; lower accuracy than ArcFace/VGG-Face. "
            "Not for race labels."
        ),
    },
    {
        "id": "SFace",
        "label": "SFace identity (optional)",
        "size": "~40 MB disk",
        "vram_short": "~0.3–0.5 GB VRAM",
        "vram": "~0.3–0.5 GB GPU if loaded",
        "category": "recognition",
        "required": False,
        "summary": "OpenCV zoo identity model.",
        "detail": "Optional recognition weights; not used for race scoring.",
    },
]
