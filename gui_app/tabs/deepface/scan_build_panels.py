"""Scan sub-tab results tree, review pane, and activity log UI."""
from __future__ import annotations

import queue
from typing import Any, Dict, Optional

import customtkinter as ctk

from gui_app.theme import C, FONT_BOLD, FONT_MONO, FONT_SM, FONT_TITLE
from gui_app.widgets import (
    _bind_tree_scroll_isolation,
    _card,
    _muted,
    _section_label,
    _stretch_columns,
    _tree_frame,
)


class DeepfaceScanBuildPanelsMixin:
    def _build_deepface_scan_panels(self, bottom) -> None:
        res_card = _card(bottom)
        res_card.grid(row=0, column=0, sticky="nsew", padx=(2, 4), pady=2)
        res_card.grid_columnconfigure(0, weight=1)
        res_card.grid_rowconfigure(1, weight=1)
        _section_label(res_card, "Hits (select to review)").pack(
            anchor="w", padx=14, pady=(12, 4)
        )
        wrap, tree = _tree_frame(res_card)
        wrap.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        cols = ("name", "state", "race", "face", "conf", "verdict", "id")
        tree["columns"] = cols
        tree["show"] = "headings"
        widths = [140, 45, 80, 70, 50, 90, 50]
        labels = {
            "name": "NAME", "state": "ST", "race": "LISTED", "face": "FACE",
            "conf": "CONF", "verdict": "VERDICT", "id": "ID",
        }
        for c, w in zip(cols, widths):
            tree.heading(c, text=labels.get(c, c.upper()))
            tree.column(c, width=w, minwidth=36, stretch=(c == "name"))
        _stretch_columns(tree, cols, widths)
        self.df_scan_tree = tree
        self._df_scan_hits_by_iid: Dict[str, Any] = {}
        self._df_scan_image_refs: list = []
        tree.bind("<<TreeviewSelect>>", self._deepface_scan_on_select)
        _bind_tree_scroll_isolation(tree, wrap)

        rev_card = _card(bottom)
        rev_card.grid(row=0, column=1, sticky="nsew", padx=4, pady=2)
        _section_label(rev_card, "Review / live scan").pack(
            anchor="w", padx=14, pady=(12, 4)
        )
        _muted(
            rev_card,
            "While scanning, shows the mugshot currently being scored. "
            "Click a hit in the list to pin it for confirm/skip. "
            "Verdicts sync to Browse → Reports.",
        ).pack(anchor="w", padx=14, pady=(0, 6))
        self._df_scan_live_preview = True
        self._df_scan_live_seq = 0

        rev_body = ctk.CTkFrame(rev_card, fg_color="transparent")
        rev_body.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        rev_body.grid_columnconfigure(1, weight=1)
        rev_body.grid_rowconfigure(1, weight=1)

        photo_wrap = ctk.CTkFrame(
            rev_body, fg_color=C["tree_bg"], corner_radius=10, width=160, height=200,
        )
        photo_wrap.grid(row=0, column=0, rowspan=2, sticky="nw", padx=(0, 12), pady=4)
        photo_wrap.grid_propagate(False)
        self.df_scan_photo_lbl = ctk.CTkLabel(
            photo_wrap, text="Start a scan\nto preview", font=FONT_SM, text_color=C["dim"],
        )
        self.df_scan_photo_lbl.place(relx=0.5, rely=0.5, anchor="center")

        self.df_scan_review_name = ctk.CTkLabel(
            rev_body, text="—", font=FONT_TITLE, text_color=C["text"], anchor="w",
        )
        self.df_scan_review_name.grid(row=0, column=1, sticky="ew", pady=(4, 2))

        self.df_scan_review_meta = ctk.CTkLabel(
            rev_body,
            text="Scan to live-preview each mugshot, or select a hit to review.",
            font=FONT_SM, text_color=C["muted"], anchor="nw", justify="left", wraplength=320,
        )
        self.df_scan_review_meta.grid(row=1, column=1, sticky="new", pady=(0, 6))

        self.df_scan_review_verdict = ctk.CTkLabel(
            rev_body, text="", font=FONT_BOLD, text_color=C["dim"], anchor="w",
        )
        self.df_scan_review_verdict.grid(row=2, column=1, sticky="ew", pady=(0, 6))

        btn_row = ctk.CTkFrame(rev_card, fg_color="transparent")
        btn_row.pack(fill="x", padx=12, pady=(0, 12))
        self.df_scan_btn_confirm = ctk.CTkButton(
            btn_row, text="Confirmed incorrect", width=150,
            command=lambda: self._deepface_scan_set_verdict("confirmed"),
            fg_color="#5c3030", hover_color="#7a4040", text_color=C["text"], state="disabled",
        )
        self.df_scan_btn_confirm.pack(side="left", padx=(0, 6))
        self.df_scan_btn_correct = ctk.CTkButton(
            btn_row, text="Confirmed correct", width=140,
            command=lambda: self._deepface_scan_set_verdict("correct"),
            fg_color="#2a4a38", hover_color="#356348", text_color=C["text"], state="disabled",
        )
        self.df_scan_btn_correct.pack(side="left", padx=(0, 6))
        self.df_scan_btn_skip = ctk.CTkButton(
            btn_row, text="Skip", width=70,
            command=lambda: self._deepface_scan_set_verdict("skip"),
            fg_color=C["elevated"], hover_color=C["border"], text_color=C["muted"],
            border_width=1, border_color=C["border"], state="disabled",
        )
        self.df_scan_btn_skip.pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            btn_row, text="Next unreviewed", width=120,
            command=self._deepface_scan_next_unreviewed,
            fg_color=C["elevated"], hover_color=C["border"], text_color=C["text"],
            border_width=1, border_color=C["border"],
        ).pack(side="right")

        log_card = _card(bottom)
        log_card.grid(row=0, column=2, sticky="nsew", padx=(4, 2), pady=2)
        _section_label(log_card, "Scan activity").pack(
            anchor="w", padx=14, pady=(12, 4)
        )
        self.df_scan_log = ctk.CTkTextbox(
            log_card, font=FONT_MONO, fg_color=C["bg"], text_color=C["muted"],
            border_color=C["border"], border_width=1, corner_radius=8,
        )
        self.df_scan_log.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.df_scan_log.configure(state="disabled")
        self._df_scan_log_queue: queue.Queue = queue.Queue()
        self._df_scan_selected_iid: Optional[str] = None
        if not hasattr(self, "_report_verdicts") or self._report_verdicts is None:
            self._report_verdicts = {}
        if hasattr(self, "_load_report_verdicts"):
            try:
                self._load_report_verdicts()
            except Exception:
                pass
        self.after(120, self._deepface_poll_scan_log)
