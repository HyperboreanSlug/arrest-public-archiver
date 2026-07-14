"""RecentlyBooked Misclassify UI and actual-race override."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import customtkinter as ctk

from gui_app.shared.record_sidebar import (
    RecordSidebar,
    merge_race_manual_flags,
)
from gui_app.theme import C, FONT_SM
from gui_app.widgets import (
    _enable_tree_column_sort,
    _hpaned,
    _stretch_columns,
    _tree_frame,
    tree_iid_for_record,
    tree_selected_record,
)
from scraper.database import Database


class RbMisclassifyMixin:
    def _build_rb_misclassify(self, tab):
        bar = ctk.CTkFrame(tab, fg_color=C["panel"])
        bar.pack(fill="x", padx=8, pady=8)
        ctk.CTkLabel(
            bar, text="Stated race", font=FONT_SM, text_color=C["muted"]
        ).pack(side="left", padx=(8, 3), pady=8)
        race_values = ["All"]
        try:
            race_values = ["All"] + Database(self.db_path).distinct_race_labels()
        except Exception:
            pass
        self.rb_mc_stated_race = ctk.CTkComboBox(
            bar, values=race_values, width=130
        )
        self.rb_mc_stated_race.set("All")
        self.rb_mc_stated_race.pack(side="left", padx=(0, 8), pady=8)
        ctk.CTkButton(bar, text="Analyze", command=self._rb_analyze).pack(
            side="left", padx=5
        )
        self.rb_mc_status = ctk.CTkLabel(
            bar,
            text="Surname misclass for all mugshot sources; filter by stated race.",
            font=FONT_SM,
            text_color=C["muted"],
        )
        self.rb_mc_status.pack(side="left", padx=12)

        pane = _hpaned(tab)
        pane.pack(fill="both", expand=True, padx=8, pady=8)
        left = ctk.CTkFrame(pane, fg_color="transparent")
        wrap, self.rb_mc_tree = _tree_frame(left)
        wrap.pack(fill="both", expand=True)
        cols = ["name", "race", "likely", "conf", "charge", "state"]
        self.rb_mc_tree.configure(columns=cols)
        _enable_tree_column_sort(self.rb_mc_tree, cols)
        _stretch_columns(self.rb_mc_tree, cols, [180, 90, 100, 60, 180, 50])
        self.rb_mc_sidebar = RecordSidebar(pane)
        self.rb_mc_sidebar.bind_after(self.after)
        self.rb_mc_sidebar.bind_verdict(
            lambda rec, verdict: self._rb_apply_verdict(
                rec,
                verdict,
                tree=self.rb_mc_tree,
                records=self._rb_mc_records,
                sidebar=self.rb_mc_sidebar,
                remove_from_list=True,
            )
        )
        self.rb_mc_sidebar.bind_actual_race(self._rb_mc_set_actual_race)
        pane.add(left, minsize=360, stretch="always")
        pane.add(self.rb_mc_sidebar.frame, minsize=400, stretch="always")
        self._rb_mc_records: List[Dict[str, Any]] = []

        def on_select(_event=None):
            record = tree_selected_record(self.rb_mc_tree)
            if record is None:
                self.rb_mc_sidebar.clear()
                return
            self.rb_mc_sidebar.show(record)

        self.rb_mc_tree.bind("<<TreeviewSelect>>", on_select)

    def _rb_mc_set_actual_race(self, record: Dict[str, Any], actual: str) -> None:
        actual = (actual or "").strip() or "Unknown"
        record["likely_ethnicity"] = actual
        flags_json = merge_race_manual_flags(record.get("flags"))
        record["flags"] = flags_json
        rid = record.get("id")
        source_url = str(record.get("source_url") or "").strip()
        for existing in self._rb_mc_records:
            same_id = record.get("id") and existing.get("id") == record.get("id")
            same_url = source_url and existing.get("source_url") == source_url
            if same_id or same_url or existing is record:
                existing["likely_ethnicity"] = actual
                existing["flags"] = flags_json
                iid = tree_iid_for_record(self.rb_mc_tree, existing)
                if iid is not None:
                    vals = list(self.rb_mc_tree.item(iid, "values"))
                    if len(vals) >= 3:
                        vals[2] = actual
                        self.rb_mc_tree.item(iid, values=vals)
                break
        if rid is None and source_url:
            db = Database(self.db_path)
            try:
                row = db._conn.execute(
                    "SELECT id FROM arrests WHERE source_url = ? LIMIT 1",
                    (source_url,),
                ).fetchone()
                if row:
                    rid = row["id"] if hasattr(row, "keys") else row[0]
                    record["id"] = int(rid)
            finally:
                db.close()
        if rid is not None:
            try:
                self.db.update_arrest(
                    int(rid),
                    {"likely_ethnicity": actual, "flags": flags_json},
                )
                self.log(f"RB misclass actual race set: {actual}")
            except Exception as exc:
                self.log(f"Could not save actual race: {exc}")
        else:
            self.log(f"RB misclass actual race set (not in DB): {actual}")

    def _rb_mc_race_filter(self) -> Optional[str]:
        race = (
            getattr(self, "rb_mc_stated_race", None).get()
            if getattr(self, "rb_mc_stated_race", None)
            else "All"
        )
        if race in (None, "", "All"):
            return None
        return str(race)
