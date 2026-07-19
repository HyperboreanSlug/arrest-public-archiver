"""Arrest record search."""
from __future__ import annotations

import customtkinter as ctk

from gui_app.tabs.recentlybooked.full_scrape_flow import FlowRow, after_idle_reflow
from gui_app.theme import C, FONT_SM
from gui_app.widgets import _enable_tree_column_sort, _stretch_columns, _tree_frame
from scraper.charge_classifications import list_category_choices
from scraper.charge_summary import summarize_charge
from scraper.database.date_window import resolve_cutoff
from scraper.searcher import ArrestSearcher, format_race_label


class SearchTabMixin:
    def _build_search(self, tab):
        tab.configure(fg_color=C["surface"])
        bar = ctk.CTkFrame(tab, fg_color=C["panel"])
        bar.pack(fill="x", padx=8, pady=8)
        flow = FlowRow(bar, padx=5, pady=4)
        host = flow.host

        self.search_name = ctk.CTkEntry(host, placeholder_text="Name", width=140)
        self.search_state = ctk.CTkEntry(host, placeholder_text="State", width=70)
        self.search_race = ctk.CTkEntry(host, placeholder_text="Race", width=100)
        self.search_charge = ctk.CTkComboBox(
            host, values=list_category_choices(), width=160
        )
        self.search_charge.set("all")
        self.search_window_amount = ctk.CTkEntry(
            host, width=52, placeholder_text="any"
        )
        self.search_window_unit = ctk.CTkComboBox(
            host, values=["days", "weeks"], width=78
        )
        self.search_window_unit.set("days")
        search_btn = ctk.CTkButton(host, text="Search", command=self._run_search)
        last_lbl = ctk.CTkLabel(
            host, text="Last", font=FONT_SM, text_color=C["muted"]
        )
        for w in (
            self.search_name,
            self.search_state,
            self.search_race,
            self.search_charge,
            last_lbl,
            self.search_window_amount,
            self.search_window_unit,
            search_btn,
        ):
            flow.add(w)
        after_idle_reflow(self, flow)
        bar.bind("<Configure>", lambda _e: flow.reflow(), add="+")
        self.search_window_amount.bind("<Return>", lambda _e: self._run_search())
        self.search_name.bind("<Return>", lambda _e: self._run_search())

        wrap, self.search_tree = _tree_frame(tab)
        wrap.pack(fill="both", expand=True, padx=8, pady=8)
        cols = [
            "id",
            "name",
            "race",
            "charge",
            "category",
            "state",
            "date",
            "source",
        ]
        self.search_tree.configure(columns=cols)
        _enable_tree_column_sort(self.search_tree, cols)
        _stretch_columns(
            self.search_tree, cols, [70, 200, 120, 240, 160, 65, 110, 130]
        )
        self.search_tree.bind("<Double-1>", self._open_search_detail)

    def _search_since_date(self):
        try:
            return resolve_cutoff(
                self.search_window_amount.get(),
                self.search_window_unit.get(),
            )
        except Exception:
            return None

    def _run_search(self):
        since = self._search_since_date()
        s = ArrestSearcher(self.db_path)
        r = s.search(
            name=self.search_name.get(),
            state=self.search_state.get(),
            race=self.search_race.get(),
            charge_category=self.search_charge.get(),
            since_date=since,
            limit=1000,
        )
        s.close()
        self.search_tree.delete(*self.search_tree.get_children())
        for x in r.records:
            name = x.get("full_name") or (
                f"{x.get('first_name') or ''} {x.get('last_name') or ''}".strip()
            )
            if name:
                name = str(name).upper()
            self.search_tree.insert(
                "",
                "end",
                values=(
                    x["id"],
                    name,
                    format_race_label(x.get("race") or ""),
                    summarize_charge(x),
                    x.get("charge_category") or "",
                    x.get("state") or "",
                    x.get("arrest_date") or x.get("booking_date") or "",
                    x.get("source_system") or "",
                ),
            )

    def _open_search_detail(self, _event):
        sel = self.search_tree.selection()
        if sel:
            from gui_app.shared.detail_drawer import show_arrest_drawer

            show_arrest_drawer(
                self,
                self.db.get_arrest_by_id(
                    int(self.search_tree.item(sel[0], "values")[0])
                ),
            )
