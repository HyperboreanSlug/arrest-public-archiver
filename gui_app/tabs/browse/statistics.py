"""Archive statistics view."""
from __future__ import annotations
import customtkinter as ctk
from gui_app.theme import C
from gui_app.widgets import _card, _misclass_race_bucket, _render_bar_chart, _render_pie_chart

class StatisticsTabMixin:
    def _build_statistics(self, tab):
        tab.configure(fg_color=C["surface"])
        ctk.CTkButton(tab, text="Analyze", command=self._analyze_statistics).pack(anchor="w", padx=10, pady=10)
        self.stats_status = ctk.CTkLabel(tab, text="Analyze distributions and charge categories.", text_color=C["muted"])
        self.stats_status.pack(anchor="w", padx=10)
        self.stats_body = ctk.CTkScrollableFrame(tab, fg_color=C["surface"]); self.stats_body.pack(fill="both", expand=True, padx=8, pady=8)

    def _analyze_statistics(self):
        for w in self.stats_body.winfo_children(): w.destroy()
        races = self.db.get_race_distribution(); charges = self.db.get_charge_category_distribution()
        buckets = {}
        for row in races: buckets[_misclass_race_bucket(row.get("race"))] = buckets.get(_misclass_race_bucket(row.get("race")), 0) + int(row.get("count") or 0)
        total = self.db.get_total_count()
        self.stats_status.configure(text=f"{total:,} arrests")
        for title, rows, fn in (("Recorded race buckets", list(buckets.items()), _render_pie_chart),
                                ("Charge categories", [(r["label"], r["count"]) for r in charges], _render_bar_chart),
                                ("States", [(r.get("state") or "Unknown", r["count"]) for r in self.db.get_state_distribution()], _render_bar_chart)):
            image = fn(rows, title=title)
            card = _card(self.stats_body); card.pack(fill="x", padx=4, pady=5)
            ctk.CTkLabel(card, text="", image=image).pack(padx=8, pady=8)
