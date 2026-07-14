"""Shared RecentlyBooked helpers: rows, filters, split pane, append row."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import customtkinter as ctk

from gui_app.shared.record_sidebar import RecordSidebar
from gui_app.widgets import (
    _enable_tree_column_sort,
    _hpaned,
    _stretch_columns,
    _tree_frame,
    tree_row_bind,
    tree_selected_record,
)
from scraper.charge_summary import summarize_charge
from scraper.searcher import ArrestSearcher, _is_compatible, format_race_label

from .constants import _RB_COLS, _RB_WIDTHS


class RbCommonMixin:
    def _rb_hint(self, record: Dict[str, Any], eth=None) -> str:
        if eth is None:
            eth = ArrestSearcher(self.db_path).ethnic_db
        n = self._rb_name(record)
        last = (record.get("last_name") or "").strip()
        if not last and n:
            last = n.split()[-1]
        first = (record.get("first_name") or "").strip() or None
        likely, conf, _ = eth.classify_by_name(last, first_name=first)
        race = record.get("race") or ""
        hint = f"{likely} {conf:.0%}"
        if (
            likely != "Unknown"
            and race
            and not _is_compatible(likely, race, record.get("ethnicity"))
        ):
            hint = f"FLAG {hint} vs {format_race_label(race)}"
        return hint

    @staticmethod
    def _rb_name(record: Dict[str, Any]) -> str:
        return (
            record.get("full_name")
            or f"{record.get('first_name') or ''} {record.get('last_name') or ''}".strip()
            or "—"
        )

    def _rb_row_values(self, record: Dict[str, Any], eth=None) -> tuple:
        return (
            self._rb_name(record),
            format_race_label(record.get("race") or ""),
            record.get("state") or "",
            record.get("county") or "",
            summarize_charge(record),
            self._rb_hint(record, eth),
        )

    def _rb_split(
        self, parent, *, records_attr: str, tree_attr: str, sidebar_attr: str,
        remove_on_verdict: bool = False,
    ):
        """Tree on the left, photo/details sidebar on the right."""
        pane = _hpaned(parent)
        pane.pack(fill="both", expand=True, padx=8, pady=8)
        left = ctk.CTkFrame(pane, fg_color="transparent")
        wrap, tree = _tree_frame(left)
        wrap.pack(fill="both", expand=True)
        tree.configure(columns=_RB_COLS)
        _enable_tree_column_sort(tree, _RB_COLS)
        _stretch_columns(tree, _RB_COLS, _RB_WIDTHS)
        sidebar = RecordSidebar(pane)
        sidebar.bind_after(self.after)
        sidebar.bind_verdict(
            lambda rec, verdict: self._rb_apply_verdict(
                rec,
                verdict,
                tree=tree,
                records=getattr(self, records_attr),
                sidebar=sidebar,
                remove_from_list=remove_on_verdict,
            )
        )
        pane.add(left, minsize=360, stretch="always")
        pane.add(sidebar.frame, minsize=400, stretch="always")
        setattr(self, records_attr, [])
        setattr(self, tree_attr, tree)
        setattr(self, sidebar_attr, sidebar)

        def on_select(_event=None):
            record = tree_selected_record(tree)
            if record is None:
                sidebar.clear()
                return
            sidebar.show(record)

        tree.bind("<<TreeviewSelect>>", on_select)
        return tree, sidebar

    def _rb_append_row(
        self,
        tree,
        records: List[Dict[str, Any]],
        record: Dict[str, Any],
        *,
        eth=None,
        sidebar: Optional[RecordSidebar] = None,
        select_latest: bool = False,
        status_label=None,
        status_fmt: str = "{n} records",
    ) -> None:
        records.append(record)
        item = tree.insert("", "end", values=self._rb_row_values(record, eth))
        tree_row_bind(tree, item, record)
        if status_label is not None:
            status_label.configure(text=status_fmt.format(n=len(records)))
        if select_latest:
            tree.selection_set(item)
            tree.see(item)
            if sidebar is not None:
                sidebar.show(record)

    @staticmethod
    def _rb_has_race(record: Dict[str, Any]) -> bool:
        return bool(str(record.get("race") or "").strip())

    @staticmethod
    def _rb_has_photo(record: Dict[str, Any]) -> bool:
        """True only for a real mugshot file on disk — not missing or placeholder."""
        from scraper.mugshot_ethnicity.photo_quality import record_has_real_photo

        return record_has_real_photo(record)

    @classmethod
    def _rb_filter_rows(
        cls,
        rows: List[Dict[str, Any]],
        *,
        hide_no_race: bool = False,
        hide_no_photo: bool = False,
    ) -> List[Dict[str, Any]]:
        out = rows
        if hide_no_race:
            out = [r for r in out if cls._rb_has_race(r)]
        if hide_no_photo:
            out = [r for r in out if cls._rb_has_photo(r)]
        return out

    @staticmethod
    def _rb_filter_mode_text(*, hide_no_race: bool, hide_no_photo: bool) -> str:
        parts = []
        if hide_no_race:
            parts.append("no-race")
        if hide_no_photo:
            parts.append("no-photo")
        if not parts:
            return "showing all"
        return "hiding " + " + ".join(parts)
