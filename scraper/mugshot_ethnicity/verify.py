"""Combine name-based ethnicity with mugshot scores (verify workflow)."""
from __future__ import annotations

from scraper.mugshot_ethnicity.verify_batch import verify_misclassifications
from scraper.mugshot_ethnicity.verify_record import verify_record

__all__ = [
    "verify_record",
    "verify_misclassifications",
]
