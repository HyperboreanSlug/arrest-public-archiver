"""Persistent application settings."""
from __future__ import annotations
from tkinter import filedialog
import customtkinter as ctk
from gui_app.theme import C
from scraper.app_settings import save_settings
from scraper.database import backup_database_file

class SettingsTabMixin:
    def _build_settings(self,tab):
        tab.configure(fg_color=C["surface"]);form=ctk.CTkScrollableFrame(tab,fg_color=C["surface"]);form.pack(fill="both",expand=True,padx=10,pady=10)
        self.set_db=ctk.CTkEntry(form,width=650);self.set_db.insert(0,self.db_path);self._setting(form,"Database path",self.set_db)
        ctk.CTkButton(form,text="Browse…",command=self._choose_db).pack(anchor="w",padx=8)
        self.set_backup=ctk.CTkCheckBox(form,text="Back up database when closing");self._check(self.set_backup,"backup_on_close");self.set_backup.pack(anchor="w",padx=8,pady=8)
        self.set_auto=ctk.CTkCheckBox(form,text="Auto-import open-data scrapes");self._check(self.set_auto,"scrape_auto_import");self.set_auto.pack(anchor="w",padx=8,pady=8)
        self.set_skip=ctk.CTkCheckBox(form,text="Skip existing source URLs");self._check(self.set_skip,"scrape_skip_existing");self.set_skip.pack(anchor="w",padx=8,pady=8)
        self.set_rb_photos=ctk.CTkCheckBox(form,text="RecentlyBooked: download photos");self._check(self.set_rb_photos,"rb_with_photos");self.set_rb_photos.pack(anchor="w",padx=8,pady=8)
        self.set_rb_html=ctk.CTkCheckBox(form,text="RecentlyBooked: archive HTML");self._check(self.set_rb_html,"rb_with_html");self.set_rb_html.pack(anchor="w",padx=8,pady=8)
        self.set_rb_delay=ctk.CTkEntry(form);self.set_rb_delay.insert(0,str(self.app_settings["rb_delay"]));self._setting(form,"RecentlyBooked delay (seconds)",self.set_rb_delay)
        self.set_rb_threads=ctk.CTkEntry(form);self.set_rb_threads.insert(0,str(self.app_settings.get("rb_threads",4)));self._setting(form,"RecentlyBooked scrape threads",self.set_rb_threads)
        ctk.CTkButton(form,text="Save settings",command=self._save_settings).pack(anchor="w",padx=8,pady=8);ctk.CTkButton(form,text="Back up now",command=self._backup_now).pack(anchor="w",padx=8,pady=4)
        self.settings_status=ctk.CTkLabel(form,text="",text_color=C["muted"]);self.settings_status.pack(anchor="w",padx=8,pady=8)
    def _setting(self,parent,label,widget):ctk.CTkLabel(parent,text=label,text_color=C["muted"]).pack(anchor="w",padx=8,pady=(8,1));widget.pack(anchor="w",padx=8)
    def _check(self,w,key):w.select() if self.app_settings.get(key) else w.deselect()
    def _choose_db(self):
        p=filedialog.asksaveasfilename(defaultextension=".db",filetypes=[("SQLite database","*.db")])
        if p:self.set_db.delete(0,"end");self.set_db.insert(0,p)
    def _save_settings(self):
        self.app_settings.update(db_path=self.set_db.get().strip(),backup_on_close=bool(self.set_backup.get()),scrape_auto_import=bool(self.set_auto.get()),scrape_skip_existing=bool(self.set_skip.get()),rb_with_photos=bool(self.set_rb_photos.get()),rb_with_html=bool(self.set_rb_html.get()))
        try:self.app_settings["rb_delay"]=float(self.set_rb_delay.get())
        except ValueError:pass
        try:self.app_settings["rb_threads"]=int(self.set_rb_threads.get())
        except ValueError:pass
        save_settings(self.app_settings)
        if self.db_path!=self.app_settings["db_path"]:self.reopen_database(self.app_settings["db_path"])
        self.settings_status.configure(text="Saved.")
    def _backup_now(self):
        try:p=backup_database_file(self.db_path,self.app_settings.get("backup_dir","data/backups"),keep=self.app_settings.get("max_backups",10),open_db=self.db);self.settings_status.configure(text=f"Backup created: {p[0]}")
        except Exception as e:self.settings_status.configure(text=f"Backup failed: {e}")
