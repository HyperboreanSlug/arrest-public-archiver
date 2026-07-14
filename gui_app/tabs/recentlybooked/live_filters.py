"""RecentlyBooked Live Feed filter state, tree rebuild, and poll tick."""
from __future__ import annotations

from typing import Any, Dict, Optional

from gui_app.widgets import tree_row_bind, tree_rows_reset

from .constants import _RB_LIVE_POLL_MS


class RbLiveFiltersMixin:
    def _rb_live_filter_flags(self) -> tuple[bool, bool]:
        hide_race = bool(
            getattr(self, "rb_live_hide_no_race_var", None)
            and self.rb_live_hide_no_race_var.get()
        )
        hide_photo = bool(
            getattr(self, "rb_live_hide_no_photo_var", None)
            and self.rb_live_hide_no_photo_var.get()
        )
        return hide_race, hide_photo

    def _rb_live_update_filter_status(self, *, log: bool = True) -> None:
        shown = len(self._rb_records)
        total = len(self._rb_live_all)
        hide_race, hide_photo = self._rb_live_filter_flags()
        mode = self._rb_filter_mode_text(
            hide_no_race=hide_race, hide_no_photo=hide_photo
        )
        srcs = self._rb_live_selected_sources()
        src_bit = f"{len(srcs)} source(s)" if srcs else "no sources"
        self.rb_live_status.configure(
            text=f"Live feed: {shown}/{total} shown ({mode}, {src_bit})."
        )
        if log:
            self.log(f"Live feed filter: {mode} · {src_bit} ({shown}/{total}).")

    def _rb_live_on_race_filter_toggle(self):
        self._rb_rebuild_live_tree()
        self._rb_live_update_filter_status()

    def _rb_live_on_photo_filter_toggle(self):
        self._rb_rebuild_live_tree()
        self._rb_live_update_filter_status()

    def _rb_live_row_matches_sources(self, rec: Dict[str, Any]) -> bool:
        selected = set(self._rb_live_selected_sources())
        if not selected:
            return False
        src = str(rec.get("source_system") or "").strip().lower()
        if not src:
            # Older RB rows may lack source_system; treat as recentlybooked.
            src = "recentlybooked"
        return src in selected

    def _rb_rebuild_live_tree(self, *, select_url: Optional[str] = None) -> None:
        eth = getattr(self, "_rb_live_eth", None)
        hide_race, hide_photo = self._rb_live_filter_flags()
        source_filtered = [
            r for r in (self._rb_live_all or []) if self._rb_live_row_matches_sources(r)
        ]
        shown = self._rb_filter_rows(
            source_filtered,
            hide_no_race=hide_race,
            hide_no_photo=hide_photo,
        )
        self._rb_records = shown
        self.rb_tree.delete(*self.rb_tree.get_children())
        tree_rows_reset(self.rb_tree)
        select_item = None
        select_rec = None
        for rec in shown:
            item = self.rb_tree.insert(
                "", "end", values=self._rb_row_values(rec, eth)
            )
            tree_row_bind(self.rb_tree, item, rec)
            if select_url and str(rec.get("source_url") or "") == select_url:
                select_item = item
                select_rec = rec
        if select_item:
            self.rb_tree.selection_set(select_item)
            self.rb_tree.see(select_item)
            self.rb_live_sidebar.show(select_rec)
        elif not shown:
            self.rb_live_sidebar.clear("No rows match filter.")

    def _rb_live_tick(self):
        try:
            if bool(self.rb_live_auto_var.get()) and not self._rb_live_busy:
                self._rb_refresh(True)
        except Exception:
            pass
        try:
            self._rb_live_poll_after = self.after(
                _RB_LIVE_POLL_MS, self._rb_live_tick
            )
        except Exception:
            self._rb_live_poll_after = None
