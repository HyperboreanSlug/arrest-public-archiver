"""Selectable DeepFace weight / detector options with accurate guidance.

Pipeline (mugshot race tools)
  1. Face detector  — finds/crops the face in the photo (pick ONE)
  2. Race weights   — classifies the crop into ethnicity labels (required)

One vs multiple downloads
  • Default: download Race only + one detector (RetinaFace). That is enough.
  • Detectors: mutually exclusive — only the selected one runs; do not download all.
  • Attribute models (Age/Gender/Emotion): separate nets; do NOT improve race.
  • Recognition models (VGG-Face, ArcFace, …): identity match only; not race.
    If you ever need identity, download ONE recognition model, not several.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from scraper.mugshot_ethnicity.weights_data import (
    DETECTOR_CACHE_FILES,
    DETECTOR_OPTIONS,
    DOWNLOAD_GUIDANCE,
    WEIGHT_CACHE_FILES,
    WEIGHT_MODELS,
)
from scraper.mugshot_ethnicity.weights_status import (
    all_detector_local_status,
    all_weight_local_status,
    detector_dropdown_label,
    detector_local_status,
    weight_local_status,
    weights_dir,
)


def detector_ids() -> List[str]:
    return [d["id"] for d in DETECTOR_OPTIONS]


def weight_model_ids() -> List[str]:
    return [m["id"] for m in WEIGHT_MODELS]


def get_detector(det_id: str) -> Optional[Dict[str, Any]]:
    for d in DETECTOR_OPTIONS:
        if d["id"] == det_id:
            return d
    return None


def get_weight_model(model_id: str) -> Optional[Dict[str, Any]]:
    for m in WEIGHT_MODELS:
        if m["id"] == model_id:
            return m
    return None


def default_selected_weights() -> List[str]:
    return ["Race"]


def explain_detector(det_id: str) -> str:
    d = get_detector(det_id)
    if not d:
        return ""
    st = detector_local_status(det_id)
    local = st.get("label") or "Unknown"
    return (
        f"{d['summary']}\n\n{d['detail']}\n\n"
        f"Disk: {d['size']}  ·  Speed: {d['speed']}\n"
        f"VRAM / memory: {d['vram']}\n"
        f"Local cache: {local}\n"
        f"Only one detector runs at a time — switching reuses that choice for scans."
    )


def explain_weight(model_id: str) -> str:
    m = get_weight_model(model_id)
    if not m:
        return DOWNLOAD_GUIDANCE
    if m.get("required"):
        req = "Required — download this for race tools"
    elif m.get("category") == "recognition":
        req = "Optional identity model — not used for race; pick at most one if needed"
    else:
        req = "Optional attribute — not used for race tools"
    st = weight_local_status(model_id)
    local = st.get("label") or "Unknown"
    return (
        f"{m['summary']}\n\n{m['detail']}\n\n"
        f"Category: {m['category']}  ·  {req}\n"
        f"Disk: {m['size']}\n"
        f"VRAM / memory when loaded: {m['vram']}\n"
        f"Local cache: {local}\n\n"
        f"{DOWNLOAD_GUIDANCE}"
    )


__all__ = [
    "WEIGHT_CACHE_FILES",
    "DETECTOR_CACHE_FILES",
    "DETECTOR_OPTIONS",
    "WEIGHT_MODELS",
    "DOWNLOAD_GUIDANCE",
    "weights_dir",
    "weight_local_status",
    "detector_local_status",
    "all_weight_local_status",
    "all_detector_local_status",
    "detector_dropdown_label",
    "detector_ids",
    "weight_model_ids",
    "get_detector",
    "get_weight_model",
    "default_selected_weights",
    "explain_detector",
    "explain_weight",
]
