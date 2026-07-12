"""Review DeepFace hits and optionally correct recorded race."""
from __future__ import annotations
from pathlib import Path
import customtkinter as ctk
from gui_app.theme import C
from gui_app.widgets import _enable_tree_column_sort,_stretch_columns,_tree_frame

class DeepfaceReportsTabMixin:
    def _build_deepface_reports(self,tab):
        tab.configure(fg_color=C["surface"]); top=ctk.CTkFrame(tab,fg_color=C["panel"]);top.pack(fill="x",padx=8,pady=8)
        self.dfr_state=ctk.CTkEntry(top,placeholder_text="State (all)");self.dfr_source=ctk.CTkEntry(top,placeholder_text="Source (all)")
        self.dfr_state.pack(side="left",padx=5,pady=8);self.dfr_source.pack(side="left",padx=5,pady=8)
        ctk.CTkButton(top,text="Refresh hits",command=self._refresh_deepface_reports).pack(side="left",padx=5)
        ctk.CTkButton(top,text="Confirm race",command=lambda:self._resolve_deepface(True)).pack(side="left",padx=5)
        ctk.CTkButton(top,text="Reject hit",command=lambda:self._resolve_deepface(False)).pack(side="left",padx=5)
        wrap,self.dfr_tree=_tree_frame(tab);wrap.pack(fill="both",expand=True,padx=8,pady=8)
        cols=["id","name","recorded","predicted","confidence","state","source","reason"];self.dfr_tree.configure(columns=cols);_enable_tree_column_sort(self.dfr_tree,cols);_stretch_columns(self.dfr_tree,cols)
        self.dfr_tree.bind("<<TreeviewSelect>>",self._show_deepface_photo)
        self.dfr_photo=ctk.CTkLabel(tab,text="Select a hit to preview its mugshot.",text_color=C["muted"]);self.dfr_photo.pack(pady=(0,8))
        self._refresh_deepface_reports()
    def _refresh_deepface_reports(self):
        rows=self.db.list_deepface_hits(state=self.dfr_state.get().strip() or None,source_system=self.dfr_source.get().strip() or None)
        self._dfr_rows={int(r["id"]):r for r in rows};self.dfr_tree.delete(*self.dfr_tree.get_children())
        for r in rows:
            d=r["_deepface"];name=r.get("full_name") or f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip()
            self.dfr_tree.insert("","end",values=(r["id"],name,r.get("race") or "",d.get("predicted_label") or d.get("top_label") or "",f"{float(d.get('top_confidence') or 0):.1%}",r.get("state") or "",r.get("source_system") or "",d.get("reason") or ""))
    def _show_deepface_photo(self,_event):
        sel=self.dfr_tree.selection()
        if not sel:return
        r=self._dfr_rows.get(int(self.dfr_tree.item(sel[0],"values")[0]));p=Path(r.get("photo_path") or "") if r else None
        if not p or not p.is_file():self.dfr_photo.configure(text="Mugshot is not available.");return
        try:self.dfr_photo.configure(text="",image=ctk.CTkImage(light_image=__import__("PIL.Image",fromlist=["Image"]).open(p),dark_image=__import__("PIL.Image",fromlist=["Image"]).open(p),size=(180,180)))
        except Exception:self.dfr_photo.configure(text=f"Mugshot: {p}")
    def _resolve_deepface(self,confirm):
        sel=self.dfr_tree.selection()
        if not sel:return
        row=self._dfr_rows[int(self.dfr_tree.item(sel[0],"values")[0])];scan=row["_deepface"];fields={"flags":("deepface-confirmed" if confirm else "deepface-rejected")}
        if confirm and scan.get("predicted_label"):fields["race"]=scan["predicted_label"]
        self.db.update_arrest(int(row["id"]),fields);self._refresh_deepface_reports();self._refresh_db_status()
