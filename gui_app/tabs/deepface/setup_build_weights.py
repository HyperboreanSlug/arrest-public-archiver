"""DeepFace Setup weights & face-detector selection UI."""
from __future__ import annotations

from typing import Dict

import customtkinter as ctk

from gui_app.theme import C, FONT_SM
from gui_app.widgets import _card, _section_label


class DeepfaceSetupBuildWeightsMixin:
    def _build_deepface_setup_weights(self, root) -> None:
        w_card = _card(root)
        w_card.pack(fill="x", padx=4, pady=(0, 8))
        _section_label(w_card, "Weights & face detector").pack(
            anchor="w", padx=14, pady=(12, 4)
        )
        from scraper.mugshot_ethnicity.weights_catalog import (
            DETECTOR_OPTIONS,
            DOWNLOAD_GUIDANCE,
            WEIGHT_MODELS,
            detector_dropdown_label,
            detector_local_status,
            explain_detector,
            explain_weight,
            weight_local_status,
        )

        guide = ctk.CTkLabel(
            w_card, text=DOWNLOAD_GUIDANCE, font=FONT_SM, text_color=C["muted"],
            anchor="w", justify="left", wraplength=920,
        )
        guide.pack(fill="x", padx=14, pady=(0, 10))

        sett = getattr(self, "app_settings", {}) or {}
        det_default = str(sett.get("deepface_detector") or "retinaface")
        det_labels = [detector_dropdown_label(d) for d in DETECTOR_OPTIONS]
        det_id_by_label = {
            detector_dropdown_label(d): d["id"] for d in DETECTOR_OPTIONS
        }
        label_by_det_id = {
            d["id"]: detector_dropdown_label(d) for d in DETECTOR_OPTIONS
        }
        self._df_det_id_by_label = det_id_by_label
        self._df_label_by_det_id = label_by_det_id
        self._df_detector_options = DETECTOR_OPTIONS

        det_row = ctk.CTkFrame(w_card, fg_color="transparent")
        det_row.pack(fill="x", padx=14, pady=(0, 6))
        ctk.CTkLabel(
            det_row,
            text="Face detector (one only · VRAM · download status)",
            font=FONT_SM, text_color=C["muted"],
        ).pack(side="left", padx=(0, 8))
        self.df_detector_var = ctk.StringVar(
            value=label_by_det_id.get(det_default, det_labels[0])
        )
        self.df_detector_combo = ctk.CTkComboBox(
            det_row, variable=self.df_detector_var, values=det_labels, width=480,
            fg_color=C["bg"], border_color=C["border"], button_color=C["elevated"],
            text_color=C["text"], dropdown_fg_color=C["panel"],
            command=self._deepface_on_detector_change,
        )
        self.df_detector_combo.pack(side="left")

        det_st = detector_local_status(det_default)
        self.df_detector_status = ctk.CTkLabel(
            det_row, text=det_st.get("label") or "", font=FONT_SM,
            text_color=C["success"] if det_st.get("downloaded") else C["danger"],
            anchor="w",
        )
        self.df_detector_status.pack(side="left", padx=(12, 0))

        self.df_detector_help = ctk.CTkLabel(
            w_card, text=explain_detector(det_default), font=FONT_SM,
            text_color=C["dim"], anchor="w", justify="left", wraplength=920,
        )
        self.df_detector_help.pack(fill="x", padx=14, pady=(0, 10))

        ctk.CTkLabel(
            w_card,
            text=(
                "Model weights (check boxes, then Download selected weights). "
                "Green “Downloaded” = file present under ~/.deepface/weights. "
                "Race alone is enough for ethnicity tools."
            ),
            font=FONT_SM, text_color=C["muted"], anchor="w",
            wraplength=920, justify="left",
        ).pack(fill="x", padx=14, pady=(4, 4))

        saved_models = {
            p.strip()
            for p in str(sett.get("deepface_weight_models") or "Race").split(",")
            if p.strip()
        }
        if "Race" not in saved_models:
            saved_models.add("Race")

        self._df_weight_vars: Dict[str, ctk.BooleanVar] = {}
        self._df_weight_status_labels: Dict[str, ctk.CTkLabel] = {}
        self._df_weight_summary_labels: Dict[str, ctk.CTkLabel] = {}
        weights_frame = ctk.CTkFrame(w_card, fg_color="transparent")
        weights_frame.pack(fill="x", padx=10, pady=(0, 6))

        left_col = ctk.CTkFrame(weights_frame, fg_color="transparent")
        right_col = ctk.CTkFrame(weights_frame, fg_color="transparent")
        left_col.pack(side="left", fill="both", expand=True, padx=(4, 8))
        right_col.pack(side="left", fill="both", expand=True, padx=(8, 4))

        for i, m in enumerate(WEIGHT_MODELS):
            parent = left_col if i % 2 == 0 else right_col
            mid = m["id"]
            var = ctk.BooleanVar(value=(mid in saved_models) or bool(m.get("required")))
            self._df_weight_vars[mid] = var
            row = ctk.CTkFrame(parent, fg_color=C["elevated"], corner_radius=8)
            row.pack(fill="x", pady=3)
            vram = m.get("vram_short") or m.get("vram") or ""
            size = m.get("size") or ""
            st = weight_local_status(mid)
            st_label = st.get("label") or "Not downloaded"
            st_ok = bool(st.get("downloaded"))

            head = ctk.CTkFrame(row, fg_color="transparent")
            head.pack(fill="x", padx=10, pady=(8, 2))
            cb = ctk.CTkCheckBox(
                head,
                text=f"{m['label']}  ·  {size}" + (f"  ·  {vram}" if vram else ""),
                variable=var, font=FONT_SM, text_color=C["text"],
                fg_color=C["accent"], hover_color=C["accent_hover"],
                border_color=C["border"], checkmark_color=C["bg"],
                command=lambda mid=mid: self._deepface_on_weight_toggle(mid),
            )
            cb.pack(side="left", anchor="w")
            if m.get("required"):
                try:
                    cb.configure(state="disabled")
                except Exception:
                    pass
            badge = ctk.CTkLabel(
                head, text=("✓ " + st_label) if st_ok else st_label, font=FONT_SM,
                text_color=C["success"] if st_ok else C["danger"], anchor="e",
            )
            badge.pack(side="right", padx=(8, 0))
            self._df_weight_status_labels[mid] = badge

            cat = m.get("category") or ""
            cat_note = {
                "attribute": "Attribute model",
                "recognition": "Identity model (not race)",
            }.get(cat, cat)
            sum_lbl = ctk.CTkLabel(
                row,
                text=f"{m['summary']}\n{cat_note} · disk {size} · load {vram}",
                font=FONT_SM, text_color=C["dim"], anchor="w",
                wraplength=420, justify="left",
            )
            sum_lbl.pack(fill="x", padx=14, pady=(0, 8))
            self._df_weight_summary_labels[mid] = sum_lbl

        self.df_weight_help = ctk.CTkLabel(
            w_card, text=explain_weight("Race"), font=FONT_SM,
            text_color=C["muted"], anchor="nw", justify="left", wraplength=920,
        )
        self.df_weight_help.pack(fill="x", padx=14, pady=(4, 12))
