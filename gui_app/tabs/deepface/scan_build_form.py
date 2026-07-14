"""Scan sub-tab option form widgets (filters, checkboxes, controls)."""
from __future__ import annotations

from typing import Any, Dict

import customtkinter as ctk

from gui_app.theme import C, FONT_SM


class DeepfaceScanBuildFormMixin:
    def _build_deepface_scan_form(self, opt, sett: Dict[str, Any]) -> None:
        grid = ctk.CTkFrame(opt, fg_color="transparent")
        grid.pack(fill="x", padx=14, pady=(0, 8))
        for c in range(4):
            grid.grid_columnconfigure(c, weight=1)

        ctk.CTkLabel(grid, text="State filter", font=FONT_SM, text_color=C["muted"]).grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=2
        )
        self.df_scan_state = ctk.CTkEntry(
            grid, width=80, placeholder_text="All",
            fg_color=C["bg"], border_color=C["border"], text_color=C["text"],
        )
        self.df_scan_state.grid(row=1, column=0, sticky="ew", padx=(0, 12), pady=(0, 6))
        st0 = str(sett.get("deepface_scan_state") or "").strip()
        if st0:
            self.df_scan_state.insert(0, st0)

        ctk.CTkLabel(grid, text="Min face confidence", font=FONT_SM, text_color=C["muted"]).grid(
            row=0, column=1, sticky="w", padx=(0, 8), pady=2
        )
        self.df_scan_min_conf = ctk.CTkEntry(
            grid, width=80, placeholder_text="0.75",
            fg_color=C["bg"], border_color=C["border"], text_color=C["text"],
        )
        self.df_scan_min_conf.grid(row=1, column=1, sticky="ew", padx=(0, 12), pady=(0, 6))
        self.df_scan_min_conf.insert(0, str(sett.get("deepface_scan_min_conf") or "0.75"))

        ctk.CTkLabel(grid, text="Max candidates (0=all)", font=FONT_SM, text_color=C["muted"]).grid(
            row=0, column=2, sticky="w", padx=(0, 8), pady=2
        )
        self.df_scan_limit = ctk.CTkEntry(
            grid, width=80, placeholder_text="0",
            fg_color=C["bg"], border_color=C["border"], text_color=C["text"],
        )
        self.df_scan_limit.grid(row=1, column=2, sticky="ew", padx=(0, 12), pady=(0, 6))
        self.df_scan_limit.insert(0, str(sett.get("deepface_scan_limit") or "0"))

        ctk.CTkLabel(grid, text="Source system (blank=all)", font=FONT_SM, text_color=C["muted"]).grid(
            row=0, column=3, sticky="w", padx=(0, 8), pady=2
        )
        self.df_scan_source = ctk.CTkEntry(
            grid, width=120, placeholder_text="recentlybooked",
            fg_color=C["bg"], border_color=C["border"], text_color=C["text"],
        )
        self.df_scan_source.grid(row=1, column=3, sticky="ew", padx=(0, 0), pady=(0, 6))
        src0 = str(sett.get("deepface_scan_source") or "").strip()
        if src0:
            self.df_scan_source.insert(0, src0)

        ctk.CTkLabel(
            opt, text="Recorded race filter (scan records listed as…)",
            font=FONT_SM, text_color=C["muted"], anchor="w",
        ).pack(fill="x", padx=14, pady=(4, 2))
        race_row = ctk.CTkFrame(opt, fg_color="transparent")
        race_row.pack(fill="x", padx=14, pady=(0, 6))
        self._DF_SCAN_RACE_OPTS = [
            ("WHITE", "White"),
            ("BLACK", "Black"),
            ("ASIAN", "Asian"),
            ("HISPANIC", "Hispanic"),
            ("INDIAN", "Indian"),
            ("OTHER", "Other"),
        ]
        saved_races = {
            p.strip().upper()
            for p in str(sett.get("deepface_scan_recorded") or "WHITE").replace(";", ",").split(",")
            if p.strip()
        }
        if not saved_races:
            saved_races = {"WHITE"}
        self._df_scan_race_vars: Dict[str, ctk.BooleanVar] = {}
        for key, label in self._DF_SCAN_RACE_OPTS:
            var = ctk.BooleanVar(value=(key in saved_races))
            self._df_scan_race_vars[key] = var
            ctk.CTkCheckBox(
                race_row, text=label, variable=var, font=FONT_SM, text_color=C["text"],
                fg_color=C["accent"], hover_color=C["accent_hover"],
                border_color=C["border"], checkmark_color=C["bg"], width=90,
            ).pack(side="left", padx=(0, 10))

        ctk.CTkLabel(
            opt, text="Face labels to flag (DeepFace prediction…)",
            font=FONT_SM, text_color=C["muted"], anchor="w",
        ).pack(fill="x", padx=14, pady=(4, 2))
        face_row = ctk.CTkFrame(opt, fg_color="transparent")
        face_row.pack(fill="x", padx=14, pady=(0, 6))
        self._DF_SCAN_FACE_OPTS = [
            ("black", "Black"),
            ("indian", "Indian"),
            ("asian", "Asian"),
            ("hispanic", "Hispanic"),
            ("middle_eastern", "Mid. Eastern"),
            ("white", "White"),
        ]
        saved_faces = {
            p.strip().lower()
            for p in str(
                sett.get("deepface_scan_faces") or "black,indian,asian"
            ).replace(";", ",").split(",")
            if p.strip()
        }
        if not saved_faces:
            saved_faces = {"black", "indian", "asian"}
        self._df_scan_face_vars: Dict[str, ctk.BooleanVar] = {}
        for key, label in self._DF_SCAN_FACE_OPTS:
            var = ctk.BooleanVar(value=(key in saved_faces))
            self._df_scan_face_vars[key] = var
            ctk.CTkCheckBox(
                face_row, text=label, variable=var, font=FONT_SM, text_color=C["text"],
                fg_color=C["accent"], hover_color=C["accent_hover"],
                border_color=C["border"], checkmark_color=C["bg"], width=100,
            ).pack(side="left", padx=(0, 10))

        skip_row = ctk.CTkFrame(opt, fg_color="transparent")
        skip_row.pack(fill="x", padx=14, pady=(0, 4))
        self.df_scan_rescan = ctk.BooleanVar(
            value=bool(sett.get("deepface_scan_force_rescan", False))
        )
        ctk.CTkCheckBox(
            skip_row,
            text="Rescan already-scored mugshots (ignore stored DeepFace results)",
            variable=self.df_scan_rescan, font=FONT_SM, text_color=C["text"],
            fg_color=C["accent"], hover_color=C["accent_hover"],
            border_color=C["border"], checkmark_color=C["bg"],
        ).pack(side="left")
        self.df_scan_db_stats = ctk.CTkLabel(
            skip_row, text="", font=FONT_SM, text_color=C["dim"], anchor="e",
        )
        self.df_scan_db_stats.pack(side="right")
        self.after(80, self._deepface_scan_refresh_db_stats)

    def _build_deepface_scan_controls(self, opt) -> None:
        ctrl = ctk.CTkFrame(opt, fg_color="transparent")
        ctrl.pack(fill="x", padx=14, pady=(4, 8))
        self.df_scan_start_btn = ctk.CTkButton(
            ctrl, text="Start scan", width=120, command=self._deepface_scan_start,
            fg_color=C["accent"], hover_color=C["accent_hover"], text_color=C["bg"],
        )
        self.df_scan_start_btn.pack(side="left", padx=(0, 8))
        self.df_scan_stop_btn = ctk.CTkButton(
            ctrl, text="Stop", width=90, command=self._deepface_scan_stop,
            fg_color=C["elevated"], hover_color=C["border"], text_color=C["text"],
            border_width=1, border_color=C["border"], state="disabled",
        )
        self.df_scan_stop_btn.pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            ctrl, text="Export hits…", width=110, command=self._deepface_scan_export,
            fg_color=C["elevated"], hover_color=C["border"], text_color=C["text"],
            border_width=1, border_color=C["border"],
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            ctrl, text="Clear results", width=100, command=self._deepface_scan_clear,
            fg_color=C["elevated"], hover_color=C["border"], text_color=C["text"],
            border_width=1, border_color=C["border"],
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            ctrl, text="Open Setup →", width=110, command=self._deepface_goto_setup,
            fg_color=C["elevated"], hover_color=C["border"], text_color=C["text"],
            border_width=1, border_color=C["border"],
        ).pack(side="right")

        self.df_scan_progress = ctk.CTkProgressBar(
            opt, height=8, progress_color=C["accent"], fg_color=C["elevated"],
        )
        self.df_scan_progress.pack(fill="x", padx=14, pady=(0, 4))
        self.df_scan_progress.set(0)
        self.df_scan_status = ctk.CTkLabel(
            opt, text="Ready — configure options and click Start scan",
            font=FONT_SM, text_color=C["dim"], anchor="w",
        )
        self.df_scan_status.pack(fill="x", padx=14, pady=(0, 12))
