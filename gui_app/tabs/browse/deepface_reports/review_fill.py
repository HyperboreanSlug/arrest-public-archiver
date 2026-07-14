"""Browse → DeepFace Reports: apply selected hit into review widgets."""
from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional

from gui_app.theme import C


class DeepfaceReportsReviewFillMixin:
    """Second half of review show: photo paint, verdict label, ethnicity combo."""

    def _dfr_fill_review_ui(
        self,
        name: str,
        lines: List[str],
        html_path: Optional[Path],
        url: str,
        photo_path: Optional[Path],
        photo_raw: str,
        mc: Any,
        preserve_eth: bool,
    ) -> None:
        try:
            self.dfr_name.configure(text=name)
            self._dfr_set_meta_text("\n".join(lines))
        except Exception:
            pass

        try:
            if hasattr(self, "dfr_btn_html"):
                self.dfr_btn_html.configure(
                    state="normal" if html_path is not None else "disabled"
                )
            if hasattr(self, "dfr_btn_url"):
                self.dfr_btn_url.configure(
                    state="normal" if url else "disabled"
                )
            if hasattr(self, "dfr_btn_photo"):
                self.dfr_btn_photo.configure(
                    state="normal" if photo_path is not None else "disabled"
                )
            if hasattr(self, "dfr_btn_copy"):
                self.dfr_btn_copy.configure(state="normal")
        except Exception:
            pass

        if photo_path is not None:
            stub_reason = None
            try:
                from scraper.mugshot_ethnicity.photo_quality import placeholder_reason

                stub_reason = placeholder_reason(photo_path)
            except Exception:
                stub_reason = None
            if stub_reason:
                ok, msg = self._dfr_set_photo_image(photo_path)
                lines.append(f"⚠ PLACEHOLDER: {stub_reason}")
                lines.append(
                    "Not a real mugshot — registry white/outline stub. "
                    "Do not treat as a face hit."
                )
                if ok:
                    lines.append(f"Image OK (stub): {msg}")
                self._dfr_set_meta_text("\n".join(lines))
            else:
                ok, msg = self._dfr_set_photo_image(photo_path)
                if ok:
                    lines.append(f"Image OK: {msg}")
                    self._dfr_set_meta_text("\n".join(lines))
                else:
                    self._dfr_set_photo_placeholder(f"Photo error\n{msg[:100]}")
                    self._dfr_set_meta_text(
                        "\n".join(lines + [f"Image FAIL: {msg}"])
                    )
        else:
            self._dfr_set_photo_placeholder(
                "No photo on disk" + (f"\n{photo_raw[:60]}" if photo_raw else "")
            )

        v = self._dfr_get_verdict(mc)
        vtxt = {
            "confirmed": "● Confirmed incorrect",
            "correct": "● Confirmed correct",
            "skip": "● Skipped",
            "unreviewed": "○ Unconfirmed — choose below",
        }.get(v, "○ Unconfirmed")
        vcol = {
            "confirmed": C["danger"],
            "correct": C["success"],
            "skip": C["dim"],
            "unreviewed": C["muted"],
        }.get(v, C["muted"])
        try:
            self.dfr_verdict_lbl.configure(text=vtxt, text_color=vcol)
            for b in (self.dfr_btn_bad, self.dfr_btn_ok, self.dfr_btn_skip):
                b.configure(state="normal")
        except Exception:
            pass

        eth_cur = self._dfr_current_ethnicity(mc)
        if not preserve_eth and hasattr(self, "dfr_eth_combo"):
            try:
                eth_opts = list(
                    getattr(self, "_ETHNICITY_OPTIONS", None)
                    or self._DFR_ETHNICITY_OPTIONS
                )
                if eth_cur not in eth_opts:
                    eth_opts = [eth_cur] + eth_opts
                self._dfr_eth_updating = True
                try:
                    self.dfr_eth_combo.configure(values=eth_opts, state="normal")
                    self.dfr_eth_var.set(eth_cur)
                finally:
                    self._dfr_eth_updating = False
            except Exception:
                self._dfr_eth_updating = False
