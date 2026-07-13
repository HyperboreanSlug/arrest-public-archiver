"""Browse arrests with race / classification filters and photo sidebar."""
from __future__ import annotations

import csv
import threading
from tkinter import filedialog
from typing import Any, Dict, List, Optional

import customtkinter as ctk

from gui_app.shared.record_sidebar import (
    ACTUAL_RACE_OPTIONS,
    RecordSidebar,
    merge_ethnicity_review_flags,
    merge_race_manual_flags,
)
from gui_app.theme import C, FONT_SM
from gui_app.widgets import (
    _enable_tree_column_sort,
    _hpaned,
    _stretch_columns,
    _tree_frame,
    tree_iid_for_record,
    tree_row_bind,
    tree_row_forget,
    tree_row_record,
    tree_rows_reset,
    tree_selected_record,
)
from scraper.charge_classifications import category_label
from scraper.database import Database
from scraper.searcher import ethnicity_review_verdict, format_race_label

_BROWSE_COLS = [
    "name",
    "race",
    "actual",
    "review",
    "charge",
    "state",
    "date",
    "source",
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
_REVIEW_FILTERS = [
    "All",
    "Correct",
    "Incorrect",
    "Unreviewed",
]


class MisclassifyTabMixin:
    """Browse tab (historically named Misclassify)."""

    def _build_misclassify(self, tab):
        tab.configure(fg_color=C["surface"])
        controls = ctk.CTkFrame(tab, fg_color=C["panel"])
        controls.pack(fill="x", padx=8, pady=8)

        races = ["All"] + self._browse_race_choices()
        actuals = ["All", "(Unset)"] + list(ACTUAL_RACE_OPTIONS)
        # Prefer values already in the DB when present.
        for eth in self._browse_actual_choices():
            if eth not in actuals:
                actuals.append(eth)

        self.browse_stated_race = ctk.CTkComboBox(controls, values=races, width=120)
        self.browse_actual_race_filter = ctk.CTkComboBox(
            controls, values=actuals, width=150
        )
        self.browse_review = ctk.CTkComboBox(
            controls, values=_REVIEW_FILTERS, width=130
        )
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
            ctk.CTkLabel(
                controls, text=label, font=FONT_SM, text_color=C["muted"]
            ).pack(side="left", padx=(10, 3), pady=10)
            widget.pack(side="left", padx=(0, 6), pady=10)

        self.browse_refresh_btn = ctk.CTkButton(
            controls, text="Refresh", command=self._browse_refresh
        )
        self.browse_refresh_btn.pack(side="left", padx=8)
        ctk.CTkButton(
            controls, text="Export CSV", command=self._browse_export
        ).pack(side="left", padx=4)

        self.browse_status = ctk.CTkLabel(
            controls,
            text="Filter arrests and review with the sidebar.",
            font=FONT_SM,
            text_color=C["muted"],
        )
        self.browse_status.pack(side="left", padx=12)

        # Keep aliases used by older code paths.
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
        self._mc_results = self._browse_records  # back-compat alias
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

    def _browse_refresh(self):
        if getattr(self, "_browse_busy", False):
            return
        self._browse_busy = True
        self.browse_refresh_btn.configure(state="disabled")
        self.browse_status.configure(text="Loading…")

        stated = self.browse_stated_race.get()
        actual = self.browse_actual_race_filter.get()
        review = self.browse_review.get()
        try:
            limit = int(self.browse_limit.get() or 1000)
        except ValueError:
            limit = 1000
        limit = max(0, limit)

        def work():
            try:
                db = Database(self.db_path)
                try:
                    rows = db.search_records(
                        race=None if stated in ("All", "", None) else stated,
                        likely_ethnicity=(
                            None
                            if actual in ("All", "", None)
                            else ("unset" if actual == "(Unset)" else actual)
                        ),
                        ethnicity_review=(
                            None
                            if review in ("All", "", None)
                            else review.lower()
                        ),
                        limit=limit,
                    )
                finally:
                    db.close()
                self.after(0, lambda: self._browse_show(rows))
            except Exception as exc:
                self.after(0, lambda: self._browse_error(exc))

        threading.Thread(target=work, daemon=True).start()

    def _browse_error(self, exc: Exception):
        self._browse_busy = False
        self.browse_refresh_btn.configure(state="normal")
        self.browse_status.configure(text=f"Browse failed: {exc}")

    def _browse_show(self, rows: List[Dict[str, Any]]):
        self._browse_records = list(rows)
        self._mc_results = self._browse_records
        self.mc_tree.delete(*self.mc_tree.get_children())
        tree_rows_reset(self.mc_tree)
        for rec in self._browse_records:
            item = self.mc_tree.insert("", "end", values=self._browse_row_values(rec))
            tree_row_bind(self.mc_tree, item, rec)
        self._browse_busy = False
        self.browse_refresh_btn.configure(state="normal")
        self.browse_status.configure(text=f"{len(self._browse_records):,} arrests")
        self.browse_sidebar.clear("Select a row for photo and review.")

    def _browse_find_index(self, record: Dict[str, Any]) -> Optional[int]:
        rid = record.get("id")
        url = str(record.get("source_url") or "")
        for i, existing in enumerate(self._browse_records):
            if rid is not None and existing.get("id") == rid:
                return i
            if url and existing.get("source_url") == url:
                return i
        return None

    def _browse_sidebar_verdict(self, record: Dict[str, Any], verdict: str):
        flags_json = merge_ethnicity_review_flags(record.get("flags"), verdict)
        record["flags"] = flags_json
        rid = record.get("id")
        label = (
            "classified correctly"
            if verdict == "correct"
            else "classified incorrectly"
        )
        if rid is not None:
            try:
                self.db.update_arrest(int(rid), {"flags": flags_json})
            except Exception as exc:
                self.browse_status.configure(text=f"Could not save verdict: {exc}")
                return

        idx = self._browse_find_index(record)
        if idx is not None:
            rec = self._browse_records[idx]
            rec["flags"] = flags_json
            # Drop from list when it no longer matches the active classification filter.
            want = (self.browse_review.get() or "All").strip().lower()
            keep = True
            if want == "correct":
                keep = verdict == "correct"
            elif want == "incorrect":
                keep = verdict == "incorrect"
            elif want == "unreviewed":
                keep = False
            if not keep:
                self._browse_drop_row(idx)
            else:
                iid = tree_iid_for_record(self.mc_tree, rec)
                if iid is not None:
                    self.mc_tree.item(iid, values=self._browse_row_values(rec))
                self.browse_sidebar.show(rec)

        name = self._browse_name(record)
        self.browse_status.configure(
            text=f"Marked {name} as {label}. {len(self._browse_records):,} shown."
        )
        self.log(f"Browse review: {name} → {label}")

    def _browse_sidebar_actual_race(self, record: Dict[str, Any], actual: str):
        actual = (actual or "Unknown").strip() or "Unknown"
        record["likely_ethnicity"] = actual
        # Mark this as a human-picked race so surname analysis never clobbers it.
        flags_json = merge_race_manual_flags(record.get("flags"))
        record["flags"] = flags_json
        rid = record.get("id")
        if rid is not None:
            try:
                self.db.update_arrest(
                    int(rid),
                    {"likely_ethnicity": actual, "flags": flags_json},
                )
            except Exception as exc:
                self.browse_status.configure(text=f"Could not save actual race: {exc}")
                return
        idx = self._browse_find_index(record)
        if idx is not None:
            rec = self._browse_records[idx]
            rec["likely_ethnicity"] = actual
            rec["flags"] = flags_json
            want = (self.browse_actual_race_filter.get() or "All").strip()
            if want not in ("All", "", None) and want != "(Unset)" and want != actual:
                self._browse_drop_row(idx)
            else:
                iid = tree_iid_for_record(self.mc_tree, rec)
                if iid is not None:
                    self.mc_tree.item(iid, values=self._browse_row_values(rec))
        self.browse_status.configure(
            text=f"Actual race set to {actual}. {len(self._browse_records):,} shown."
        )
        self.log(f"Browse actual race: {self._browse_name(record)} → {actual}")

    def _browse_drop_row(self, idx: int) -> None:
        """Remove the row at list index *idx* by iid and select a neighbor."""
        if not (0 <= idx < len(self._browse_records)):
            return
        rec = self._browse_records[idx]
        iid = tree_iid_for_record(self.mc_tree, rec)
        next_iid = None
        if iid is not None:
            kids = list(self.mc_tree.get_children())
            if iid in kids:
                pos = kids.index(iid)
                if pos + 1 < len(kids):
                    next_iid = kids[pos + 1]
                elif pos - 1 >= 0:
                    next_iid = kids[pos - 1]
            self.mc_tree.delete(iid)
            tree_row_forget(self.mc_tree, iid)
        self._browse_records.pop(idx)
        if next_iid is not None:
            self.mc_tree.selection_set(next_iid)
            self.mc_tree.focus(next_iid)
            self.mc_tree.see(next_iid)
            nrec = tree_row_record(self.mc_tree, next_iid)
            if nrec is not None:
                self.browse_sidebar.show(nrec)
            else:
                self.browse_sidebar.clear("No rows left.")
        else:
            self.browse_sidebar.clear("No rows left.")

    def _browse_export(self):
        if not self._browse_records:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv")]
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as fh:
            out = csv.writer(fh)
            out.writerow(
                [
                    "name",
                    "stated_race",
                    "actual_race",
                    "classification",
                    "charge_category",
                    "state",
                    "arrest_date",
                    "source",
                ]
            )
            for rec in self._browse_records:
                out.writerow(
                    [
                        self._browse_name(rec),
                        format_race_label(rec.get("race") or ""),
                        rec.get("likely_ethnicity") or "",
                        self._browse_review_label(rec),
                        rec.get("charge_category") or "",
                        rec.get("state") or "",
                        rec.get("arrest_date") or rec.get("booking_date") or "",
                        rec.get("source_system") or "",
                    ]
                )
        self.browse_status.configure(
            text=f"Exported {len(self._browse_records):,} rows to {path}"
        )
