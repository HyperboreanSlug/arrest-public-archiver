"""Browse tab and its lazily-created views."""
from __future__ import annotations

import customtkinter as ctk

from gui_app.lazy_tabs import LazyTabHost
from gui_app.theme import C


class BrowseTabMixin:
    def _build_browse(self, tab):
        tab.configure(fg_color=C["surface"])
        view = ctk.CTkTabview(
            tab,
            fg_color=C["surface"],
            segmented_button_fg_color=C["elevated"],
            segmented_button_selected_color=C["accent_dim"],
        )
        view.pack(fill="both", expand=True, padx=6, pady=6)
        host = LazyTabHost(view)
        host.register("Browse", lambda p: self._build_misclassify(p) or True)
        host.register("Statistics", lambda p: self._build_statistics(p) or True)
        host.register("Search", lambda p: self._build_search(p) or True)
        host.register("Integrity", lambda p: self._build_integrity(p) or True)
        host.register("DeepFace", lambda p: self._build_deepface_reports(p) or True)
        view.set("Browse")
        host.ensure("Browse")
        return host
