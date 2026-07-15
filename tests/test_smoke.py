"""Smoke tests — misclassification is the primary product behavior.

Implementation lives in ``tests/smoke/*.py`` (kept ≤200 lines each).
This module re-exports every suite so::

    python -m unittest tests.test_smoke -v

and ``unittest discover -s tests`` both find the full suite once.
"""
from __future__ import annotations

import unittest

from tests.smoke._path import ROOT  # noqa: F401

from tests.smoke.charge_filter import ChargeFilterTests  # noqa: F401
from tests.smoke.charge_sanitize import ChargeSanitizeTests  # noqa: F401
from tests.smoke.database_core import DatabaseCoreTests  # noqa: F401
from tests.smoke.misclass_analyze import MisclassAnalyzeTests  # noqa: F401
from tests.smoke.normalize import NormalizeTests  # noqa: F401
from tests.smoke.photo_quality import PhotoQualityTests  # noqa: F401
from tests.smoke.mugshotscom_parse import MugshotsComParseTests  # noqa: F401
from tests.smoke.recentlybooked_parse import RecentlyBookedParseTests  # noqa: F401
from tests.smoke.schema_v3 import SchemaV3Tests  # noqa: F401

__all__ = [
    "NormalizeTests",
    "DatabaseCoreTests",
    "MisclassAnalyzeTests",
    "ChargeFilterTests",
    "ChargeSanitizeTests",
    "MugshotsComParseTests",
    "RecentlyBookedParseTests",
    "PhotoQualityTests",
    "SchemaV3Tests",
]


if __name__ == "__main__":
    unittest.main()
