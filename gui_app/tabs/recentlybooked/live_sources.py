"""RecentlyBooked Live Feed multi-select sources menu."""
from __future__ import annotations

from typing import List

import customtkinter as ctk

from gui_app.theme import C, FONT_SM

from .constants import _RB_SOURCE_OPTIONS


class RbLiveSourcesMixin:
    def _rb_live_sources_button_text(self) -> str:
        selected = self._rb_live_selected_sources()
        n = len(selected)
        total = len(_RB_SOURCE_OPTIONS)
        if n == 0:
            return "Sources (none)"
        if n == total:
            return "Sources (all)"
        name_by_id = {sid: lab for sid, lab in _RB_SOURCE_OPTIONS}
        parts = [name_by_id.get(s, s) for s in selected]
        short = ", ".join(parts)
        if len(short) > 22:
            return f"Sources ({n})"
        return f"Sources: {short}"

    def _rb_live_selected_sources(self) -> List[str]:
        vars_map = getattr(self, "_rb_live_source_vars", None) or {}
        return [
            sid
            for sid, _lab in _RB_SOURCE_OPTIONS
            if bool(vars_map.get(sid) and vars_map[sid].get())
        ]

    def _rb_live_toggle_sources_menu(self):
        popup = getattr(self, "_rb_live_sources_popup", None)
        if popup is not None:
            try:
                if popup.winfo_exists():
                    popup.destroy()
            except Exception:
                pass
            self._rb_live_sources_popup = None
            return

        btn = self.rb_live_sources_btn
        popup = ctk.CTkToplevel(btn)
        popup.withdraw()
        popup.overrideredirect(True)
        popup.configure(fg_color=C["elevated"])
        popup.attributes("-topmost", True)
        frame = ctk.CTkFrame(
            popup, fg_color=C["elevated"], border_width=1, border_color=C["border"]
        )
        frame.pack(fill="both", expand=True, padx=1, pady=1)
        ctk.CTkLabel(
            frame, text="Sources", font=FONT_SM, text_color=C["muted"]
        ).pack(anchor="w", padx=10, pady=(8, 4))
        for sid, label in _RB_SOURCE_OPTIONS:
            var = self._rb_live_source_vars[sid]
            ctk.CTkCheckBox(
                frame,
                text=label,
                variable=var,
                command=self._rb_live_on_sources_changed,
            ).pack(anchor="w", padx=12, pady=4)
        ctk.CTkLabel(
            frame,
            text=(
                "Multiple sources run in parallel; identity dedupe skips the same "
                "person across hosts. Unavailable sources fail fast."
            ),
            font=FONT_SM,
            text_color=C["muted"],
            wraplength=260,
            justify="left",
        ).pack(anchor="w", padx=10, pady=(4, 8))
        popup.update_idletasks()
        try:
            bx = btn.winfo_rootx()
            by = btn.winfo_rooty() + btn.winfo_height() + 2
            w = max(200, btn.winfo_width())
            h = frame.winfo_reqheight() + 4
            popup.geometry(f"{w}x{h}+{bx}+{by}")
        except Exception:
            pass
        popup.deiconify()
        self._rb_live_sources_popup = popup

        def _close_if_outside(event=None):
            pop = getattr(self, "_rb_live_sources_popup", None)
            if pop is None:
                return
            try:
                if not pop.winfo_exists():
                    self._rb_live_sources_popup = None
                    return
                if event is not None:
                    cur = event.widget
                    while cur is not None:
                        if cur == pop:
                            return
                        cur = getattr(cur, "master", None)
                pop.destroy()
            except Exception:
                pass
            self._rb_live_sources_popup = None

        popup.bind("<FocusOut>", lambda _e: self.after(150, _close_if_outside))
        try:
            popup.focus_force()
        except Exception:
            pass

    def _rb_live_on_sources_changed(self):
        selected = self._rb_live_selected_sources()
        if not selected and self._rb_live_source_vars:
            first = next(iter(self._rb_live_source_vars.values()))
            first.set(True)
        try:
            self.rb_live_sources_btn.configure(
                text=self._rb_live_sources_button_text()
            )
        except Exception:
            pass
        self._rb_rebuild_live_tree()
        self._rb_live_update_filter_status(log=False)
