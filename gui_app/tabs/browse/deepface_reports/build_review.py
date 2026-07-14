"""Browse → DeepFace Reports: review-pane widget construction."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import customtkinter as ctk
import tkinter as tk

from gui_app.theme import C, FONT_BOLD, FONT_SM, FONT_TITLE
from gui_app.widgets import _card, _muted, _section_label


class DeepfaceReportsBuildReviewMixin:
    """Right-hand review panel (photo, meta, verdict/ethnicity controls)."""

    def _dfr_build_review_pane(self, body) -> None:
        rev = _card(body)
        rev.grid(row=0, column=1, sticky="nsew", padx=(4, 2), pady=2)
        _section_label(rev, "Review").pack(anchor="w", padx=14, pady=(12, 4))
        _muted(
            rev,
            "Confirm incorrect = real face/race mismatch. "
            "Confirm correct = not a misclass. Verdicts sync with Browse → Reports. "
            "Hit list uses the same recorded-race / face-label rules as DeepFace → Scan. "
            "Open HTML / URL for the source page · View as grid opens Reports.",
        ).pack(anchor="w", padx=14, pady=(0, 6))

        rev_body = ctk.CTkFrame(rev, fg_color="transparent")
        rev_body.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        rev_body.grid_columnconfigure(0, weight=1)

        self._DFR_PHOTO_W = 360
        self._DFR_PHOTO_H = 300
        photo_wrap = ctk.CTkFrame(
            rev_body,
            fg_color=C["tree_bg"],
            corner_radius=10,
            width=self._DFR_PHOTO_W + 16,
            height=self._DFR_PHOTO_H + 16,
            border_width=1,
            border_color=C["border"],
        )
        photo_wrap.pack(fill="x", pady=(0, 8))
        photo_wrap.pack_propagate(False)
        self.dfr_photo_wrap = photo_wrap
        self.dfr_photo_canvas = tk.Canvas(
            photo_wrap,
            width=self._DFR_PHOTO_W,
            height=self._DFR_PHOTO_H,
            bg=C["tree_bg"],
            highlightthickness=0,
            bd=0,
        )
        self.dfr_photo_canvas.place(relx=0.5, rely=0.5, anchor="center")
        self.dfr_photo_canvas.create_text(
            self._DFR_PHOTO_W // 2,
            self._DFR_PHOTO_H // 2,
            text="Select a hit",
            fill=C["dim"],
            font=("Segoe UI", 11),
            tags=("placeholder",),
        )
        self._dfr_photo_tk = None
        self.dfr_photo = self.dfr_photo_canvas

        self.dfr_name = ctk.CTkLabel(
            rev_body, text="—", font=FONT_TITLE, text_color=C["text"], anchor="w",
        )
        self.dfr_name.pack(fill="x")
        self.dfr_meta = ctk.CTkTextbox(
            rev_body,
            height=140,
            font=FONT_SM,
            fg_color=C["bg"],
            text_color=C["text"],
            border_color=C["border"],
            border_width=1,
            corner_radius=8,
            activate_scrollbars=True,
            wrap="word",
        )
        self.dfr_meta.pack(fill="x", pady=(4, 6))
        if hasattr(self, "_make_textbox_selectable"):
            self._make_textbox_selectable(self.dfr_meta)
        self._dfr_meta_text = ""
        self._dfr_html_path: Optional[Path] = None
        self._dfr_source_url = ""
        self._dfr_photo_open_path: Optional[Path] = None

        self.dfr_verdict_lbl = ctk.CTkLabel(
            rev_body, text="", font=FONT_BOLD, text_color=C["dim"], anchor="w",
        )
        self.dfr_verdict_lbl.pack(fill="x", pady=(0, 8))

        link_row = ctk.CTkFrame(rev, fg_color="transparent")
        link_row.pack(fill="x", padx=12, pady=(0, 6))
        self.dfr_btn_html = ctk.CTkButton(
            link_row, text="Open HTML", width=90, state="disabled",
            command=self._dfr_open_html,
            fg_color=C["elevated"], hover_color=C["border"], text_color=C["text"],
            border_width=1, border_color=C["border"],
        )
        self.dfr_btn_html.pack(side="left", padx=(0, 6))
        self.dfr_btn_url = ctk.CTkButton(
            link_row, text="Open URL", width=90, state="disabled",
            command=self._dfr_open_url,
            fg_color=C["elevated"], hover_color=C["border"], text_color=C["text"],
            border_width=1, border_color=C["border"],
        )
        self.dfr_btn_url.pack(side="left", padx=(0, 6))
        self.dfr_btn_photo = ctk.CTkButton(
            link_row, text="Open photo", width=90, state="disabled",
            command=self._dfr_open_photo,
            fg_color=C["elevated"], hover_color=C["border"], text_color=C["text"],
            border_width=1, border_color=C["border"],
        )
        self.dfr_btn_photo.pack(side="left", padx=(0, 6))
        self.dfr_btn_copy = ctk.CTkButton(
            link_row, text="Copy", width=70, state="disabled",
            command=self._dfr_copy_detail,
            fg_color=C["elevated"], hover_color=C["border"], text_color=C["text"],
            border_width=1, border_color=C["border"],
        )
        self.dfr_btn_copy.pack(side="left")

        btns = ctk.CTkFrame(rev, fg_color="transparent")
        btns.pack(fill="x", padx=12, pady=(0, 12))
        self.dfr_btn_bad = ctk.CTkButton(
            btns, text="Confirmed incorrect", width=150,
            command=lambda: self._dfr_set_verdict("confirmed"),
            fg_color="#5c3030", hover_color="#7a4040", text_color=C["text"],
            state="disabled",
        )
        self.dfr_btn_bad.pack(side="left", padx=(0, 6))
        self.dfr_btn_ok = ctk.CTkButton(
            btns, text="Confirmed correct", width=140,
            command=lambda: self._dfr_set_verdict("correct"),
            fg_color="#2a4a38", hover_color="#356348", text_color=C["text"],
            state="disabled",
        )
        self.dfr_btn_ok.pack(side="left", padx=(0, 6))
        self.dfr_btn_skip = ctk.CTkButton(
            btns, text="Skip", width=70,
            command=lambda: self._dfr_set_verdict("skip"),
            fg_color=C["elevated"], hover_color=C["border"], text_color=C["muted"],
            border_width=1, border_color=C["border"],
            state="disabled",
        )
        self.dfr_btn_skip.pack(side="left")

        eth_row = ctk.CTkFrame(rev, fg_color="transparent")
        eth_row.pack(fill="x", padx=12, pady=(0, 12))
        ctk.CTkLabel(
            eth_row, text="Ethnicity", font=FONT_SM, text_color=C["muted"],
        ).pack(side="left", padx=(0, 6))
        self.dfr_eth_var = ctk.StringVar(value="Unknown")
        eth_opts = list(
            getattr(self, "_ETHNICITY_OPTIONS", None) or self._DFR_ETHNICITY_OPTIONS
        )
        self.dfr_eth_combo = ctk.CTkComboBox(
            eth_row,
            variable=self.dfr_eth_var,
            values=eth_opts,
            width=200,
            height=30,
            fg_color=C["bg"],
            border_color=C["border"],
            button_color=C["elevated"],
            text_color=C["text"],
            dropdown_fg_color=C["panel"],
            state="disabled",
            font=FONT_SM,
            command=self._dfr_on_ethnicity_change,
        )
        self.dfr_eth_combo.pack(side="left")
        ctk.CTkLabel(
            eth_row,
            text="Saved on the person · used by Reports Actual filter",
            font=FONT_SM,
            text_color=C["dim"],
        ).pack(side="left", padx=(10, 0))
