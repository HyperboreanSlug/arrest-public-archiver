"""ArrestSearcher — search and ethnic misclassification analysis."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .database import Database
from .ethnic_names import EthnicNameDatabase


@dataclass
class SearchResults:
    records: List[Dict[str, Any]]
    total_count: int
    query_time_ms: float
    filters_applied: Dict[str, str] = field(default_factory=dict)


@dataclass
class Misclassification:
    record: Dict[str, Any]
    expected_race: str  # recorded race on the arrest row
    likely_ethnicity: str  # from surname
    confidence: float
    matching_names: List[str] = field(default_factory=list)


class ArrestSearcher:
    """Search arrests and run ethnic misclassification analysis (primary purpose)."""

    def __init__(self, db_path: Optional[str] = None):
        self.db = Database(db_path)
        self.ethnic_db = EthnicNameDatabase()

    def search_by_name(
        self,
        name: str,
        state: Optional[str] = None,
        race: Optional[str] = None,
        charge_category: Optional[str] = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> SearchResults:
        start = time.time()
        records = self.db.search_by_name(
            name,
            state=state,
            race=race,
            charge_category=charge_category,
            limit=limit,
            offset=offset,
        )
        return SearchResults(
            records=records,
            total_count=len(records),
            query_time_ms=(time.time() - start) * 1000,
            filters_applied={
                "name": name,
                "state": state or "",
                "race": race or "",
                "charge_category": charge_category or "",
            },
        )

    def search(
        self,
        *,
        name: Optional[str] = None,
        state: Optional[str] = None,
        race: Optional[str] = None,
        charge_category: Optional[str] = None,
        source_system: Optional[str] = None,
        since_date: Optional[str] = None,
        limit: int = 1000,
    ) -> SearchResults:
        start = time.time()
        records = self.db.search_records(
            name=name,
            state=state,
            race=race,
            charge_category=charge_category,
            source_system=source_system,
            since_date=since_date,
            limit=limit,
        )
        return SearchResults(
            records=records,
            total_count=len(records),
            query_time_ms=(time.time() - start) * 1000,
            filters_applied={
                "name": name or "",
                "state": state or "",
                "race": race or "",
                "charge_category": charge_category or "",
                "source_system": source_system or "",
                "since_date": since_date or "",
            },
        )

    def analyze_ethnicities(
        self,
        min_confidence: float = 0.5,
        limit: int = 0,
        ethnicity_filter: Optional[str] = None,
        charge_category: Optional[str] = None,
        source_system: Optional[str] = None,
        race: Optional[str] = None,
        return_base_count: bool = False,
        named_only: bool = True,
        ethnicity_review: Optional[str] = "unreviewed",
    ):
        """Primary analysis: surname ethnicity vs recorded race on arrest rows.

        Confirmed rows are excluded by default (``ethnicity_review="unreviewed"``).
        """
        from .searcher_analyze import analyze_ethnicities_impl

        return analyze_ethnicities_impl(
            self,
            min_confidence=min_confidence,
            limit=limit,
            ethnicity_filter=ethnicity_filter,
            charge_category=charge_category,
            source_system=source_system,
            race=race,
            return_base_count=return_base_count,
            named_only=named_only,
            ethnicity_review=ethnicity_review,
        )

    def get_total_count(self) -> int:
        return self.db.get_total_count()

    def get_race_distribution(self):
        return self.db.get_race_distribution()

    def get_state_distribution(self):
        return self.db.get_state_distribution()

    def get_charge_category_distribution(self):
        return self.db.get_charge_category_distribution()

    def close(self) -> None:
        self.db.close()
