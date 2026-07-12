"""Small record-detail drawer used by browse search."""
from __future__ import annotations
import os
from pathlib import Path
import customtkinter as ctk
from gui_app.theme import C

def show_arrest_drawer(parent, record):
    if not record:return
    win=ctk.CTkToplevel(parent);win.title("Arrest details");win.geometry("600x720");win.configure(fg_color=C["surface"])
    text=ctk.CTkTextbox(win,fg_color=C["bg"],text_color=C["text"]);text.pack(fill="both",expand=True,padx=10,pady=10)
    text.insert("end","\n".join(f"{k}: {v}" for k,v in record.items() if v not in (None,"")));text.configure(state="disabled")
    row=ctk.CTkFrame(win,fg_color="transparent");row.pack(fill="x",padx=10,pady=(0,10))
    for label,key in (("Open HTML","html_path"),("Open photo","photo_path")):
        p=Path(record.get(key) or "")
        if p.is_file():ctk.CTkButton(row,text=label,command=lambda x=p:os.startfile(str(x))).pack(side="left",padx=4)
