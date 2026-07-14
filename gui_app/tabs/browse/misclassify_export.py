"""Browse tab CSV export and row drop helpers."""
from __future__ import annotations

import csv
from tkinter import filedialog
from typing import Any, Dict

from gui_app.widgets import (
    tree_iid_for_record,
    tree_row_forget,
    tree_row_record,
)
from scraper.searcher import format_race_label


class MisclassifyExportMixin:
    def _browse_drop_row(self, idx: int) -> None:
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
            out.writerow([
                "name", "stated_race", "actual_race", "classification",
                "charge_category", "state", "arrest_date", "source",
            ])
            for rec in self._browse_records:
                out.writerow([
                    self._browse_name(rec),
                    format_race_label(rec.get("race") or ""),
                    rec.get("likely_ethnicity") or "",
                    self._browse_review_label(rec),
                    rec.get("charge_category") or "",
                    rec.get("state") or "",
                    rec.get("arrest_date") or rec.get("booking_date") or "",
                    rec.get("source_system") or "",
                ])
        self.browse_status.configure(
            text=f"Exported {len(self._browse_records):,} rows to {path}"
        )
