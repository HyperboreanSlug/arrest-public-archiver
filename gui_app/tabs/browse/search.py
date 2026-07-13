"""Arrest record search."""
from __future__ import annotations
import customtkinter as ctk
from gui_app.theme import C
from gui_app.widgets import _enable_tree_column_sort, _stretch_columns, _tree_frame
from scraper.charge_classifications import list_category_choices
from scraper.searcher import ArrestSearcher, format_race_label

class SearchTabMixin:
    def _build_search(self, tab):
        tab.configure(fg_color=C["surface"]); bar = ctk.CTkFrame(tab, fg_color=C["panel"]); bar.pack(fill="x", padx=8, pady=8)
        self.search_name = ctk.CTkEntry(bar, placeholder_text="Name"); self.search_state = ctk.CTkEntry(bar, placeholder_text="State")
        self.search_race = ctk.CTkEntry(bar, placeholder_text="Race"); self.search_charge = ctk.CTkComboBox(bar, values=list_category_choices())
        for w in (self.search_name,self.search_state,self.search_race,self.search_charge): w.pack(side="left", padx=5, pady=8)
        self.search_charge.set("all"); ctk.CTkButton(bar, text="Search", command=self._run_search).pack(side="left", padx=8)
        wrap,self.search_tree=_tree_frame(tab);wrap.pack(fill="both",expand=True,padx=8,pady=8)
        cols=["id","name","race","charge","category","state","date","source"]; self.search_tree.configure(columns=cols)
        _enable_tree_column_sort(self.search_tree, cols);_stretch_columns(self.search_tree,cols,[70,200,120,240,160,65,110,130]);self.search_tree.bind("<Double-1>",self._open_search_detail)
    def _run_search(self):
        s=ArrestSearcher(self.db_path); r=s.search(name=self.search_name.get(),state=self.search_state.get(),race=self.search_race.get(),charge_category=self.search_charge.get(),limit=1000);s.close()
        self.search_tree.delete(*self.search_tree.get_children())
        for x in r.records:
            name=x.get("full_name") or f"{x.get('first_name') or ''} {x.get('last_name') or ''}".strip()
            self.search_tree.insert("","end",values=(x["id"],name,format_race_label(x.get("race") or ""),x.get("charge_description") or "",x.get("charge_category") or "",x.get("state") or "",x.get("arrest_date") or x.get("booking_date") or "",x.get("source_system") or ""))
    def _open_search_detail(self,_event):
        sel=self.search_tree.selection()
        if sel:
            from gui_app.shared.detail_drawer import show_arrest_drawer
            show_arrest_drawer(self,self.db.get_arrest_by_id(int(self.search_tree.item(sel[0],"values")[0])))
