"""Scan review photo resolve/display helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import customtkinter as ctk

from gui_app.theme import C
from gui_app.paths import ROOT


class DeepfaceScanPhotoMixin:
    def _deepface_scan_clear_review(self) -> None:
        try:
            self.df_scan_photo_lbl.configure(image=None, text="Start a scan\nto preview")
            self.df_scan_review_name.configure(text="—")
            self.df_scan_review_meta.configure(
                text="Scan to live-preview each mugshot, or select a hit to review."
            )
            self.df_scan_review_verdict.configure(text="", text_color=C["dim"])
            for name in (
                "df_scan_btn_confirm",
                "df_scan_btn_correct",
                "df_scan_btn_skip",
            ):
                w = getattr(self, name, None)
                if w is not None:
                    w.configure(state="disabled")
        except Exception:
            pass
        self._df_scan_selected_iid = None

    @staticmethod
    def _deepface_scan_resolve_photo(raw: Optional[str]) -> Optional[Path]:
        """Resolve mugshot path against cwd and project ROOT."""
        s = (raw or "").strip()
        if not s:
            return None
        candidates = [
            Path(s),
            ROOT / s,
            ROOT / s.replace("\\", "/"),
            Path.cwd() / s,
        ]
        for p in candidates:
            try:
                if p.is_file() and p.stat().st_size > 0:
                    return p.resolve()
            except OSError:
                continue
        return None

    def _deepface_scan_photo_box(self) -> tuple[int, int]:
        """Live review-label size for contain-fit (fallback 152×192)."""
        lbl = getattr(self, "df_scan_photo_lbl", None)
        max_w, max_h = 152, 192
        if lbl is not None:
            try:
                w = int(lbl.winfo_width() or 0)
                h = int(lbl.winfo_height() or 0)
                if w >= 40:
                    max_w = w
                if h >= 40:
                    max_h = h
            except Exception:
                pass
            try:
                req_w = int(lbl.cget("width") or 0)
                req_h = int(lbl.cget("height") or 0)
                if req_w > 0:
                    max_w = max(max_w, req_w)
                if req_h > 0:
                    max_h = max(max_h, req_h)
            except Exception:
                pass
        return max(40, max_w), max(40, max_h)

    def _deepface_scan_set_photo(self, photo_path: Optional[Path]) -> bool:
        """Paint mugshot into the scan review label (fit inside label box)."""
        if photo_path is None:
            try:
                self.df_scan_photo_lbl.configure(image=None, text="No photo\non disk")
            except Exception:
                pass
            return False
        try:
            from PIL import Image

            with Image.open(photo_path) as raw:
                img = raw.convert("RGB")
            max_w, max_h = self._deepface_scan_photo_box()
            try:
                resample = Image.Resampling.LANCZOS
            except AttributeError:
                resample = Image.LANCZOS  # type: ignore[attr-defined]
            img = img.copy()
            img.thumbnail((max(16, max_w - 4), max(16, max_h - 4)), resample)
            img = img.copy()
            ctk_img = ctk.CTkImage(
                light_image=img, dark_image=img, size=(img.width, img.height)
            )
            if not hasattr(self, "_df_scan_image_refs") or self._df_scan_image_refs is None:
                self._df_scan_image_refs = []
            self._df_scan_image_refs.append(ctk_img)
            if len(self._df_scan_image_refs) > 40:
                self._df_scan_image_refs = self._df_scan_image_refs[-20:]
            self.df_scan_photo_lbl.configure(image=ctk_img, text="")
            return True
        except Exception:
            try:
                self.df_scan_photo_lbl.configure(image=None, text="Photo\nerror")
            except Exception:
                pass
            return False
