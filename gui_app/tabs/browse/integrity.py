"""Database integrity and maintenance controls."""
from __future__ import annotations
import threading
import customtkinter as ctk
from gui_app.theme import C
class IntegrityTabMixin:
    def _build_integrity(self, tab):
        tab.configure(fg_color=C["surface"])
        row=ctk.CTkFrame(tab,fg_color=C["panel"]);row.pack(fill="x",padx=8,pady=8)
        for text,cmd in (("Refresh report",self._refresh_integrity),("Deduplicate",self._dedupe),("Reclassify charges",self._reclassify)):
            ctk.CTkButton(row,text=text,command=cmd).pack(side="left",padx=6,pady=8)
        self.integrity_text=ctk.CTkTextbox(tab,fg_color=C["bg"],text_color=C["text"]);self.integrity_text.pack(fill="both",expand=True,padx=8,pady=8)
        self._refresh_integrity()
    def _refresh_integrity(self):
        r=self.db.get_integrity_report();o=r["overall"];text=[f"Total arrests: {o['total']:,}"]
        text += [f"{k[5:].title()}: {o[k]:,} ({o['pct_'+k[5:]]}%)" for k in o if k.startswith("with_")]
        text += ["","\nBy state:"]+[f"{x['state']}: {x['total']:,}, race {x['pct_race']}%, names {x['pct_name']}%" for x in r["by_state"]]
        self.integrity_text.delete("1.0","end");self.integrity_text.insert("end","\n".join(text))
    def _dedupe(self):
        def work():
            try:
                r=self.db.remove_duplicates_all();self.log(f"Deduplication: {r}");self.after(0,self._refresh_integrity)
            except Exception as e:self.log(f"Deduplication failed: {e}")
        threading.Thread(target=work,daemon=True).start()
    def _reclassify(self):
        threading.Thread(target=lambda:self._reclassify_work(),daemon=True).start()
    def _reclassify_work(self):
        try:n=self.db.reclassify_charges();self.log(f"Reclassified {n:,} arrests.");self.after(0,self._refresh_integrity)
        except Exception as e:self.log(f"Charge reclassification failed: {e}")
