"""Browse tab UI construction and static helpers."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import customtkinter as ctk

from gui_app.shared.record_sidebar import ACTUAL_RACE_OPTIONS, RecordSidebar
from gui_app.theme import C, FONT_SM
from gui_app.widgets import (
    _enable_tree_column_sort,
    _hpaned,
    _stretch_columns,
    _tree_frame,
    tree_selected_record,
)
from scraper.charge_classifications import category_label
from scraper.database import Database
from scraper.searcher import ethnicity_review_verdict, format_race_label

_BROWSE_COLS = [
    "name", "race", "actual", "review", "charge", "state", "date", "source",
]
_BROWSE_LABELS = {
    "name": "Name",
    "race": "Stated race",
    "actual": "Actual race",
    "review": "Classification",
    "charge": "Charge",
    "state": "State",
    "date": "Date",
    "source": "Source",
}
_REVIEW_FILTERS = ["All", "Correct", "Incorrect", "Unreviewed"]


class MisclassifyBuildMixin:
    """Build the browse tree + sidebar layout."""

    def _build_misclassify(self, tab):
        tab.configure(fg_color=C["surface"])
        controls = ctk.CTkFrame(tab, fg_color=C["panel"])
        controls.pack(fill="x", padx=8, pady=8)

        races = ["All"] + self._browse_race_choices()
        actuals = ["All", "(Unset)"] + list(ACTUAL_RACE_OPTIONS)
        for eth in self._browse_actual_choices():
            if eth not in actuals:
                actuals.append(eth)

        self.browse_stated_race = ctk.CTkComboBox(controls, values=races, width=120)
        self.browse_actual_race_filter = ctk.CTkComboBox(controls, values=actuals, width=150)
        self.browse_review = ctk.CTkComboBox(controls, values=_REVIEW_FILTERS, width=130)
        self.browse_limit = ctk.CTkEntry(controls, width=90, placeholder_text="1000")
        self.browse_stated_race.set("All")
        self.browse_actual_race_filter.set("All")
        self.browse_review.set("All")
        self.browse_limit.insert(0, "1000")

        for label, widget in (
            ("Stated race", self.browse_stated_race),
            ("Actual race", self.browse_actual_race_filter),
            ("Classification", self.browse_review),
            ("Limit", self.browse_limit),
        ):
            ctk.CTkLabel(controls, text=label, font=FONT_SM, text_color=C["muted"]).pack(
                side="left", padx=(10, 3), pady=10
            )
            widget.pack(side="left", padx=(0, 6), pady=10)

        self.browse_refresh_btn = ctk.CTkButton(
            controls, text="Refresh", command=self._browse_refresh
        )
        self.browse_refresh_btn.pack(side="left", padx=8)
        ctk.CTkButton(controls, text="Export CSV", command=self._browse_export).pack(
            side="left", padx=4
        )

        self.browse_status = ctk.CTkLabel(
            controls, text="Filter arrests and review with the sidebar.",
            font=FONT_SM, text_color=C["muted"],
        )
        self.browse_status.pack(side="left", padx=12)

        self.mc_status = self.browse_status
        self.mc_analyze_btn = self.browse_refresh_btn

        pane = _hpaned(tab)
        pane.pack(fill="both", expand=True, padx=8, pady=8)
        left = ctk.CTkFrame(pane, fg_color="transparent")
        wrap, self.mc_tree = _tree_frame(left)
        wrap.pack(fill="both", expand=True)
        self.mc_tree.configure(columns=_BROWSE_COLS)
        _enable_tree_column_sort(self.mc_tree, _BROWSE_COLS, _BROWSE_LABELS)
        _stretch_columns(
            self.mc_tree, _BROWSE_COLS, [200, 100, 120, 110, 180, 50, 110, 120]
        )

        self.browse_sidebar = RecordSidebar(pane)
        self.browse_sidebar.bind_after(self.after)
        self.browse_sidebar.bind_verdict(self._browse_sidebar_verdict)
        self.browse_sidebar.bind_actual_race(self._browse_sidebar_actual_race)
        pane.add(left, minsize=360, stretch="always")
        pane.add(self.browse_sidebar.frame, minsize=400, stretch="always")

        self._browse_records: List[Dict[str, Any]] = []
        self._mc_results = self._browse_records
        self.mc_tree.bind("<<TreeviewSelect>>", self._browse_on_select)
        self.after(200, self._browse_refresh)

    def _browse_race_choices(self) -> List[str]:
        try:
            return Database(self.db_path).distinct_race_labels()
        except Exception:
            return []

    def _browse_actual_choices(self) -> List[str]:
        try:
            return Database(self.db_path).distinct_likely_ethnicities()
        except Exception:
            return []

    @staticmethod
    def _browse_review_label(record: Dict[str, Any]) -> str:
        verdict = ethnicity_review_verdict(record)
        if verdict == "correct":
            return "Correct"
        if verdict == "incorrect":
            return "Incorrect"
        return "Unreviewed"

    @staticmethod
    def _browse_name(record: Dict[str, Any]) -> str:
        return (
            str(record.get("full_name") or "").strip()
            or f"{record.get('first_name') or ''} {record.get('last_name') or ''}".strip()
            or "—"
        )

    def _browse_row_values(self, record: Dict[str, Any]) -> tuple:
        return (
            self._browse_name(record),
            format_race_label(record.get("race") or ""),
            record.get("likely_ethnicity") or "—",
            self._browse_review_label(record),
            category_label(record.get("charge_category") or "") or "—",
            record.get("state") or "—",
            record.get("arrest_date") or record.get("booking_date") or "—",
            record.get("source_system") or "—",
        )

    def _browse_selected_index(self) -> Optional[int]:
        record = tree_selected_record(self.mc_tree)
        if record is None:
            return None
        try:
            return self._browse_records.index(record)
        except ValueError:
            return None

    def _browse_on_select(self, _event=None):
        record = tree_selected_record(self.mc_tree)
        if record is None:
            self.browse_sidebar.clear()
            return
        self.browse_sidebar.show(record)
