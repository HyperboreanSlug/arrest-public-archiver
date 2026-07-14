"""RecentlyBooked Live Feed refresh orchestration and UI result apply."""
from __future__ import annotations

import threading
from typing import Any, Dict, List

from scraper.database import Database
from scraper.searcher import ArrestSearcher


class RbLiveRefreshMixin:
    def _rb_refresh(self, incremental: bool = False):
        if self._rb_live_busy:
            return
        sources = self._rb_live_selected_sources()
        if not sources:
            self.rb_live_status.configure(text="Live feed: select at least one source.")
            return
        self._rb_live_busy = True
        self.rb_live_status.configure(
            text="Updating…" if incremental else "Refreshing…"
        )
        if not incremental:
            self.log_live(f"Live feed: fetching ({', '.join(sources)})…")
            self._rb_live_all = []
            self._rb_records = []
            self.rb_tree.delete(*self.rb_tree.get_children())
            self.rb_live_sidebar.clear("Loading…")

        def work():
            try:
                self._rb_live_eth = ArrestSearcher(self.db_path).ethnic_db
                delay = min(0.35, float(self.app_settings.get("rb_delay") or 1.0))
                bn_delay = max(1.0, float(self.app_settings.get("rb_delay") or 1.0))
                known = {
                    str(r.get("source_url") or "")
                    for r in self._rb_live_all
                    if r.get("source_url")
                }
                try:
                    _kdb = Database(self.db_path)
                    try:
                        known |= _kdb.existing_source_urls()
                    finally:
                        _kdb.close()
                except Exception:
                    pass
                counters = {"imported": 0, "skipped": 0, "rejected": 0}
                new_rows: List[Dict[str, Any]] = []
                errors: List[str] = []
                self._rb_live_fetch(
                    sources, known, counters, new_rows, errors,
                    delay=delay, bn_delay=bn_delay, incremental=incremental,
                )
                self.after(
                    0,
                    lambda: self._rb_live_apply_results(
                        incremental, new_rows, counters, errors
                    ),
                )
            except Exception as e:
                self.log_live(f"Live feed failed: {e}")
                self.after(
                    0,
                    lambda: self.rb_live_status.configure(text=f"Failed: {e}"),
                )
            finally:
                self.after(0, lambda: setattr(self, "_rb_live_busy", False))

        threading.Thread(target=work, daemon=True).start()

    def _rb_live_apply_results(self, incremental, new_rows, counters, errors) -> None:
        if incremental:
            self._rb_live_all = new_rows + self._rb_live_all
            seen = set()
            merged = []
            for r in self._rb_live_all:
                u = str(r.get("source_url") or "")
                if u and u in seen:
                    continue
                if u:
                    seen.add(u)
                merged.append(r)
            self._rb_live_all = merged
            added_n = len(new_rows)
        else:
            self._rb_live_all = new_rows
            added_n = len(new_rows)
        self._rb_rebuild_live_tree(
            select_url=(
                str(new_rows[0].get("source_url") or "") if new_rows else None
            )
        )
        shown = len(self._rb_records)
        total = len(self._rb_live_all)
        hide_race, hide_photo = self._rb_live_filter_flags()
        mode = self._rb_filter_mode_text(
            hide_no_race=hide_race, hide_no_photo=hide_photo
        )
        imported, skipped, rejected = (
            counters["imported"], counters["skipped"], counters["rejected"]
        )
        if incremental and not new_rows and not errors:
            msg = f"Live feed: {shown}/{total} shown · no new bookings · {mode}."
        else:
            msg = (
                f"Live feed: {shown}/{total} shown"
                + (f" · +{added_n} new" if incremental else "")
                + f" · +{imported} imported · {skipped} skipped"
                + f" · {rejected} no-photo dropped · {mode}."
            )
        if errors:
            msg += f" · errors: {'; '.join(errors)}"
        self.rb_live_status.configure(text=msg)
        self.log_live(msg)
        self._refresh_db_status()
