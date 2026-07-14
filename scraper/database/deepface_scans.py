"""Persist DeepFace mugshot scan results (keyed by arrest_id)."""
from __future__ import annotations

from scraper.database.deepface_scans_ops import DeepfaceScanOpsMixin
from scraper.database.deepface_scans_schema import (
    DeepfaceScanSchemaMixin,
    photo_fingerprint,
)
from scraper.database.deepface_scans_write import DeepfaceScanWriteMixin


class DeepfaceScanMixin(
    DeepfaceScanSchemaMixin,
    DeepfaceScanWriteMixin,
    DeepfaceScanOpsMixin,
):
    """CRUD for ``deepface_scans`` table (one latest row per arrest)."""


__all__ = [
    "DeepfaceScanMixin",
    "photo_fingerprint",
]
