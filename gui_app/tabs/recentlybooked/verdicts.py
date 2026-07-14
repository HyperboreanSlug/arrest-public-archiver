"""RecentlyBooked ethnicity-review verdict persistence and UI apply."""
from __future__ import annotations

from typing import Any, Dict, List

from gui_app.shared.record_sidebar import (
    RecordSidebar,
    merge_ethnicity_review_flags,
)
from gui_app.widgets import (
    tree_iid_for_record,
    tree_row_forget,
    tree_row_record,
)
from scraper.database import Database


class RbVerdictsMixin:
    def _rb_persist_verdict(self, record: Dict[str, Any], verdict: str) -> bool:
        """Write ethnicity_review into flags; resolve id via source_url when needed."""
        flags_json = merge_ethnicity_review_flags(record.get("flags"), verdict)
        record["flags"] = flags_json
        rid = record.get("id")
        source_url = str(record.get("source_url") or "").strip()
        db = Database(self.db_path)
        try:
            if rid is None and source_url:
                row = db._conn.execute(
                    "SELECT id, flags FROM arrests WHERE source_url = ? LIMIT 1",
                    (source_url,),
                ).fetchone()
                if row:
                    rid = row["id"] if hasattr(row, "keys") else row[0]
                    existing = row["flags"] if hasattr(row, "keys") else row[1]
                    flags_json = merge_ethnicity_review_flags(existing, verdict)
                    record["flags"] = flags_json
            if rid is None:
                return False
            record["id"] = int(rid)
            return bool(db.update_arrest(int(rid), {"flags": flags_json}))
        finally:
            db.close()

    def _rb_apply_verdict(
        self,
        record: Dict[str, Any],
        verdict: str,
        *,
        tree,
        records: List[Dict[str, Any]],
        sidebar: RecordSidebar,
        remove_from_list: bool = False,
    ) -> None:
        label = (
            "classified correctly"
            if verdict == "correct"
            else "classified incorrectly"
        )
        saved = self._rb_persist_verdict(record, verdict)
        # Keep in-memory copy in sync for the current selection.
        idx = None
        matched = None
        for i, existing in enumerate(records):
            same_id = record.get("id") and existing.get("id") == record.get("id")
            same_url = (
                record.get("source_url")
                and existing.get("source_url") == record.get("source_url")
            )
            if same_id or same_url or existing is record:
                existing["flags"] = record.get("flags")
                if record.get("id") is not None:
                    existing["id"] = record["id"]
                idx = i
                matched = existing
                break

        if saved:
            self.log(f"Marked {self._rb_name(record)} as {label}.")
        else:
            self.log(
                f"Marked {self._rb_name(record)} as {label} "
                "(not in DB yet — import to persist)."
            )

        if remove_from_list and idx is not None:
            iid = tree_iid_for_record(tree, matched)
            next_iid = None
            if iid is not None:
                kids = list(tree.get_children())
                if iid in kids:
                    pos = kids.index(iid)
                    if pos + 1 < len(kids):
                        next_iid = kids[pos + 1]
                    elif pos - 1 >= 0:
                        next_iid = kids[pos - 1]
                tree.delete(iid)
                tree_row_forget(tree, iid)
            records.pop(idx)
            if next_iid is not None:
                tree.selection_set(next_iid)
                tree.focus(next_iid)
                tree.see(next_iid)
                nrec = tree_row_record(tree, next_iid)
                sidebar.show(nrec) if nrec is not None else sidebar.clear()
            else:
                sidebar.clear("No more rows.")
            return

        sidebar.show(record)
