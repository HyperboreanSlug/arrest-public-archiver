"""Browse → DeepFace Reports: tab layout and widget construction."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import customtkinter as ctk

from gui_app.theme import C, FONT_SM


class DeepfaceReportsBuildMixin:
    """UI shell for the DeepFace reports review queue."""

    # Same labels as Reports cards (manual ethnicity override)
    _DFR_ETHNICITY_OPTIONS = [
        "Asian",
        "Asian (vietnamese)",
        "Asian (chinese)",
        "Asian (korean)",
        "Asian (japanese)",
        "Asian (filipino)",
        "Indian",
        "Indian (india)",
        "Hispanic",
        "African American",
        "Arabic",
        "Jewish",
        "Portuguese",
        "European",
        "Native American",
        "Unknown",
    ]

    def _build_deepface_reports(self, tab) -> None:
        tab.configure(fg_color=C["surface"])
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        self._dfr_hits: List[Any] = []
        self._dfr_hits_by_iid: Dict[str, Any] = {}
        self._dfr_selected_iid: Optional[str] = None
        self._dfr_image_refs: list = []

        if not hasattr(self, "_report_verdicts") or self._report_verdicts is None:
            self._report_verdicts = {}
        if hasattr(self, "_load_report_verdicts"):
            try:
                self._load_report_verdicts()
            except Exception:
                pass

        self._dfr_build_toolbar(tab)
        self._dfr_build_body(tab)
        self.after(80, self._dfr_refresh)

    def _dfr_build_toolbar(self, tab) -> None:
        top = ctk.CTkFrame(tab, fg_color=C["surface"])
        top.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))

        bar = ctk.CTkFrame(top, fg_color="transparent")
        bar.pack(fill="x", padx=4, pady=(0, 4))

        ctk.CTkButton(
            bar, text="Refresh hits", width=110,
            command=self._dfr_refresh,
            fg_color=C["accent"], hover_color=C["accent_hover"], text_color=C["bg"],
        ).pack(side="left", padx=(0, 8))

        ctk.CTkLabel(bar, text="Show", font=FONT_SM, text_color=C["muted"]).pack(
            side="left", padx=(4, 4)
        )
        self.dfr_verdict_filter = ctk.StringVar(value="All")
        ctk.CTkComboBox(
            bar, variable=self.dfr_verdict_filter, width=150,
            values=["Unconfirmed", "Confirmed incorrect", "Confirmed correct", "Skip", "All"],
            fg_color=C["bg"], border_color=C["border"], button_color=C["elevated"],
            text_color=C["text"], dropdown_fg_color=C["panel"],
            command=lambda _v: self._dfr_apply_filters(),
        ).pack(side="left", padx=(0, 8))

        ctk.CTkLabel(bar, text="Face", font=FONT_SM, text_color=C["muted"]).pack(
            side="left", padx=(4, 4)
        )
        self.dfr_face_filter = ctk.StringVar(value="All")
        ctk.CTkComboBox(
            bar, variable=self.dfr_face_filter, width=120,
            values=["All", "black", "indian", "asian", "hispanic", "middle_eastern", "white"],
            fg_color=C["bg"], border_color=C["border"], button_color=C["elevated"],
            text_color=C["text"], dropdown_fg_color=C["panel"],
            command=lambda _v: self._dfr_apply_filters(),
        ).pack(side="left", padx=(0, 8))

        ctk.CTkLabel(bar, text="State", font=FONT_SM, text_color=C["muted"]).pack(
            side="left", padx=(4, 4)
        )
        self.dfr_state = ctk.CTkEntry(
            bar, width=56, placeholder_text="All",
            fg_color=C["bg"], border_color=C["border"], text_color=C["text"],
        )
        self.dfr_state.pack(side="left", padx=(0, 8))
        self.dfr_state.bind("<Return>", lambda _e: self._dfr_refresh())

        ctk.CTkLabel(bar, text="Source", font=FONT_SM, text_color=C["muted"]).pack(
            side="left", padx=(4, 4)
        )
        self.dfr_source = ctk.CTkEntry(
            bar, width=110, placeholder_text="All",
            fg_color=C["bg"], border_color=C["border"], text_color=C["text"],
        )
        _src0 = ""
        try:
            _sett = getattr(self, "app_settings", None) or {}
            _src0 = str(_sett.get("deepface_scan_source") or "").strip()
        except Exception:
            _src0 = ""
        if _src0:
            self.dfr_source.insert(0, _src0)
        self.dfr_source.pack(side="left", padx=(0, 8))
        self.dfr_source.bind("<Return>", lambda _e: self._dfr_refresh())

        ctk.CTkLabel(bar, text="Min conf", font=FONT_SM, text_color=C["muted"]).pack(
            side="left", padx=(4, 4)
        )
        self.dfr_min_conf = ctk.CTkEntry(
            bar, width=56, placeholder_text="0.75",
            fg_color=C["bg"], border_color=C["border"], text_color=C["text"],
        )
        _min_default = "0.75"
        try:
            sett = getattr(self, "app_settings", None) or {}
            if not sett:
                from scraper.app_settings import load_settings

                sett = load_settings()
            _min_default = str(sett.get("deepface_scan_min_conf") or "0.75")
        except Exception:
            pass
        self.dfr_min_conf.insert(0, _min_default)
        self.dfr_min_conf.pack(side="left", padx=(0, 8))
        self.dfr_min_conf.bind("<Return>", lambda _e: self._dfr_apply_filters())

        ctk.CTkButton(
            bar, text="Apply", width=70,
            command=self._dfr_apply_filters,
            fg_color=C["elevated"], hover_color=C["border"], text_color=C["text"],
            border_width=1, border_color=C["border"],
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            bar, text="Next unreviewed", width=120,
            command=self._dfr_next_unreviewed,
            fg_color=C["elevated"], hover_color=C["border"], text_color=C["text"],
            border_width=1, border_color=C["border"],
        ).pack(side="right", padx=(6, 0))
        ctk.CTkButton(
            bar, text="View as grid", width=110,
            command=self._dfr_view_as_grid,
            fg_color=C["elevated"], hover_color=C["border"], text_color=C["text"],
            border_width=1, border_color=C["border"],
        ).pack(side="right")

        metrics = ctk.CTkFrame(top, fg_color="transparent")
        metrics.pack(fill="x", padx=4, pady=(0, 4))
        self.dfr_m_total = ctk.CTkLabel(
            metrics, text="Hits: —", font=FONT_SM, text_color=C["text"]
        )
        self.dfr_m_total.pack(side="left", padx=(0, 12))
        self.dfr_m_open = ctk.CTkLabel(
            metrics, text="Open: —", font=FONT_SM, text_color=C["muted"]
        )
        self.dfr_m_open.pack(side="left", padx=(0, 12))
        self.dfr_m_bad = ctk.CTkLabel(
            metrics, text="Incorrect: —", font=FONT_SM, text_color=C["danger"]
        )
        self.dfr_m_bad.pack(side="left", padx=(0, 12))
        self.dfr_m_ok = ctk.CTkLabel(
            metrics, text="Correct: —", font=FONT_SM, text_color=C["success"]
        )
        self.dfr_m_ok.pack(side="left", padx=(0, 12))
        self.dfr_status = ctk.CTkLabel(
            metrics, text="Stored DeepFace scan hits (from DeepFace → Scan).",
            font=FONT_SM, text_color=C["dim"],
        )
        self.dfr_status.pack(side="left", fill="x", expand=True)

    def _dfr_build_body(self, tab) -> None:
        body = ctk.CTkFrame(tab, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)
        self._dfr_build_list_pane(body)
        self._dfr_build_review_pane(body)
