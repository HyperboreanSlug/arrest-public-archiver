"""Search arrest records and detect ethnic surname vs race misclassifications.

Primary product purpose: flag potential race/ethnicity misclassifications
when a published arrest record's surname strongly suggests one ethnicity
but the recorded race field is incompatible.
"""
from __future__ import annotations

from .searcher_core import ArrestSearcher as _ArrestSearcherBase
from .searcher_core import Misclassification, SearchResults
from .searcher_export import ArrestSearcherFull, SexOffenderSearcher, get_searcher
from .searcher_names import (
    _first_name_from_record,
    _last_name_from_record,
    _middle_name_from_record,
    ethnicity_review_verdict,
)
from .searcher_race import (
    _ETHNICITY_COMPATIBLE_RACES,
    _RACE_ALIASES,
    _canonical_race_key,
    _ethnicity_family,
    _has_hispanic_ethnicity,
    _is_compatible,
    _is_other_or_other_asian,
    format_race_label,
)

# Public class includes export mixin (same API as pre-split ArrestSearcher).
ArrestSearcher = ArrestSearcherFull

__all__ = [
    "SearchResults",
    "Misclassification",
    "ArrestSearcher",
    "SexOffenderSearcher",
    "get_searcher",
    "format_race_label",
    "ethnicity_review_verdict",
    "_canonical_race_key",
    "_is_compatible",
    "_ethnicity_family",
    "_last_name_from_record",
    "_first_name_from_record",
    "_middle_name_from_record",
    "_ETHNICITY_COMPATIBLE_RACES",
    "_RACE_ALIASES",
    "_has_hispanic_ethnicity",
    "_is_other_or_other_asian",
    "_ArrestSearcherBase",
]
