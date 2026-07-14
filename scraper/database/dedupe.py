"""Dedupe / merge helpers for arrest rows (composed mixins)."""
from __future__ import annotations

from scraper.database.dedupe_cross import DedupeCrossMixin
from scraper.database.dedupe_identity import DedupeIdentityMixin
from scraper.database.dedupe_identity_ops import DedupeIdentityOpsMixin
from scraper.database.dedupe_merge import DedupeMergeMixin


class DedupeMixin(
    DedupeCrossMixin,
    DedupeIdentityOpsMixin,
    DedupeIdentityMixin,
    DedupeMergeMixin,
):
    """Public dedupe API composed from merge / identity / cross mixins."""


__all__ = ["DedupeMixin"]
