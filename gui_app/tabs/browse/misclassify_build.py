"""Browse tab UI construction and static helpers."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import customtkinter as ctk

from gui_app.shared.record_sidebar import RecordSidebar
from gui_app.tabs.browse.misclassify_constants import (
    BROWSE_ACTUAL_RACES,
    BROWSE_COLS,
    BROWSE_LABELS,
    VERIFICATION_FILTERS,
    bucket_actual_race,
    verification_label,
    verification_query,
)
from gui_app.theme import C, FONT_SM
from gui_app.widgets import (
    _enable_tree_column_sort,
    _hpaned,
    _stretch_columns,
    _tree_frame,
    tree_selected_record,
)
from scraper.charge_summary import summarize_charge
from scraper.database import Database
from scraper.searcher import format_race_label


class MisclassifyBuildMixin:
    """Build the browse tree + sidebar layout."""

    def _build_misclassify(self, tab):
        tab.configure(fg_color=C["surface"])
        controls = ctk.CTkFrame(tab, fg_color=C["panel"])
        controls.pack(fill="x", padx=8, pady=8)

        races = ["All"] + self._browse_race_choices()
        actuals = ["All", "(Unset)"] + list(BROWSE_ACTUAL_RACES)

        self.browse_stated_race = ctk.CTkComboBox(
            controls, values=races, width=120, command=self._browse_filter_changed
        )
        self.browse_actual_race_filter = ctk.CTkComboBox(
            controls, values=actuals, width=120, command=self._browse_filter_changed
        )
        self.browse_review = ctk.CTkComboBox(
            controls,
            values=VERIFICATION_FILTERS,
            width=170,
            command=self._browse_filter_changed,
        )
        # 0 / blank = no cap (load full filtered list)
        self.browse_limit = ctk.CTkEntry(controls, width=90, placeholder_text="0 = all")
        self.browse_stated_race.set("All")
        self.browse_actual_race_filter.set("All")
        self.browse_review.set("Unverified")
        self.browse_limit.insert(0, "0")
        self.browse_misclass_only = ctk.CTkCheckBox(
            controls,
            text="Suspected misclassifications only",
            font=FONT_SM,
            command=self._browse_filter_changed,
        )

        for label, widget in (
            ("Stated race", self.browse_stated_race),
            ("Actual race", self.browse_actual_race_filter),
            ("Confirmation", self.browse_review),
            ("Limit (0=all)", self.browse_limit),
        ):
            ctk.CTkLabel(controls, text=label, font=FONT_SM, text_color=C["muted"]).pack(
                side="left", padx=(10, 3), pady=10
            )
            widget.pack(side="left", padx=(0, 6), pady=10)

        self.browse_misclass_only.pack(side="left", padx=(10, 8), pady=10)
        self.browse_refresh_btn = ctk.CTkButton(
            controls, text="Refresh", command=self._browse_refresh
        )
        self.browse_refresh_btn.pack(side="left", padx=8)
        ctk.CTkButton(controls, text="Export CSV", command=self._browse_export).pack(
            side="left", padx=4
        )

        self.browse_status = ctk.CTkLabel(
            controls,
            text="Filter arrests and review with the sidebar. Confirmed stay out of Unverified.",
            font=FONT_SM,
            text_color=C["muted"],
        )
        self.browse_status.pack(side="left", padx=12)

        self.mc_status = self.browse_status
        self.mc_analyze_btn = self.browse_refresh_btn

        pane = _hpaned(tab)
        pane.pack(fill="both", expand=True, padx=8, pady=8)
        left = ctk.CTkFrame(pane, fg_color="transparent")
        wrap, self.mc_tree = _tree_frame(left)
        wrap.pack(fill="both", expand=True)
        self.mc_tree.configure(columns=BROWSE_COLS)
        _enable_tree_column_sort(self.mc_tree, BROWSE_COLS, BROWSE_LABELS)
        _stretch_columns(
            self.mc_tree, BROWSE_COLS, [200, 100, 120, 140, 180, 50, 110, 120]
        )

        self.browse_sidebar = RecordSidebar(pane)
        # Coarse actual-race buckets only on Browse (not the long ethnicity list).
        self.browse_sidebar._actual_race_options = list(BROWSE_ACTUAL_RACES)
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

    def _browse_filter_changed(self, _choice: str = "") -> None:
        if getattr(self, "_browse_busy", False):
            return
        self._browse_refresh()

    @staticmethod
    def _browse_verification_query(label: Optional[str]) -> Optional[str]:
        return verification_query(label)

    @staticmethod
    def _browse_review_label(record: Dict[str, Any]) -> str:
        return verification_label(record)

    @staticmethod
    def _browse_name(record: Dict[str, Any]) -> str:
        return (
            str(record.get("full_name") or "").strip()
            or f"{record.get('first_name') or ''} {record.get('last_name') or ''}".strip()
            or "—"
        )

    def _browse_row_values(self, record: Dict[str, Any]) -> tuple:
        raw_actual = (record.get("likely_ethnicity") or "").strip()
        actual = bucket_actual_race(raw_actual) or raw_actual or "—"
        return (
            self._browse_name(record),
            format_race_label(record.get("race") or ""),
            actual,
            self._browse_review_label(record),
            summarize_charge(record),
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
