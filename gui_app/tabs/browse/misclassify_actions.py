"""Browse tab refresh, verdict, actual-race actions."""
from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

from gui_app.shared.record_sidebar import (
    merge_ethnicity_review_flags,
    merge_race_manual_flags,
)
from gui_app.widgets import tree_iid_for_record, tree_row_bind, tree_rows_reset
from scraper.database import Database


class MisclassifyActionsMixin:
    """Async refresh and sidebar review handlers."""

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
                            None if review in ("All", "", None) else review.lower()
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
            "classified correctly" if verdict == "correct" else "classified incorrectly"
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
        flags_json = merge_race_manual_flags(record.get("flags"))
        record["flags"] = flags_json
        rid = record.get("id")
        if rid is not None:
            try:
                self.db.update_arrest(
                    int(rid), {"likely_ethnicity": actual, "flags": flags_json}
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
