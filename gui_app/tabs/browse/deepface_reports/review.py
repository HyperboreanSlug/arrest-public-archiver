"""Browse → DeepFace Reports: selection and detail panel fill."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from gui_app.theme import C
from gui_app.widgets import _format_race_display, _format_state_display
from gui_app.paths import ROOT


class DeepfaceReportsReviewMixin:
    """Clear/show review pane and tree selection handlers."""

    def _dfr_clear_review(self) -> None:
        try:
            self._dfr_set_photo_placeholder("Select a hit")
            self.dfr_name.configure(text="—")
            self._dfr_set_meta_text("")
            self.dfr_verdict_lbl.configure(text="", text_color=C["dim"])
            for b in (
                self.dfr_btn_bad,
                self.dfr_btn_ok,
                self.dfr_btn_skip,
                getattr(self, "dfr_btn_html", None),
                getattr(self, "dfr_btn_url", None),
                getattr(self, "dfr_btn_photo", None),
                getattr(self, "dfr_btn_copy", None),
            ):
                if b is not None:
                    b.configure(state="disabled")
            self._dfr_html_path = None
            self._dfr_source_url = ""
            self._dfr_photo_open_path = None
            if hasattr(self, "dfr_eth_combo"):
                self.dfr_eth_combo.configure(state="disabled")
            if hasattr(self, "dfr_eth_var"):
                self.dfr_eth_var.set("Unknown")
        except Exception:
            pass

    def _dfr_set_meta_text(self, text: str) -> None:
        """Write selectable detail text into the review textbox."""
        self._dfr_meta_text = text or ""
        body = getattr(self, "dfr_meta", None)
        if body is None:
            return
        try:
            body.configure(state="normal")
            body.delete("1.0", "end")
            if text:
                body.insert("1.0", text)
            if hasattr(self, "_detail_hide_unneeded_scrollbars"):
                self.after(
                    30, lambda b=body: self._detail_hide_unneeded_scrollbars(b)
                )
        except Exception:
            pass

    @staticmethod
    def _dfr_resolve_existing_path(raw: Optional[str]) -> Optional[Path]:
        """Resolve relative archived HTML/file paths against ROOT and cwd."""
        s = (raw or "").strip()
        if not s:
            return None
        candidates = [
            Path(s),
            Path(s.replace("/", "\\")),
            Path(s.replace("\\", "/")),
            ROOT / s,
            ROOT / s.replace("\\", "/"),
            Path.cwd() / s,
            Path.cwd() / s.replace("\\", "/"),
        ]
        for p in candidates:
            try:
                if p.is_file() and p.stat().st_size > 0:
                    return p.resolve()
            except OSError:
                continue
        return None

    def _dfr_on_select(self, _event=None) -> None:
        try:
            sel = self.dfr_tree.selection()
            if not sel:
                return
            iid = sel[0]
            mc = self._dfr_hits_by_iid.get(iid)
            if mc is None:
                return
            self._dfr_show(iid, mc)
        except Exception:
            pass

    def _dfr_select_initial(self) -> None:
        """Pick first unreviewed hit, else first row — always show a photo if possible."""
        if not hasattr(self, "dfr_tree"):
            return
        kids = list(self.dfr_tree.get_children() or [])
        if not kids:
            self._dfr_clear_review()
            return
        pick = None
        for iid in kids:
            mc = self._dfr_hits_by_iid.get(iid)
            if mc is not None and self._dfr_get_verdict(mc) == "unreviewed":
                pick = iid
                break
        if pick is None:
            pick = kids[0]
        try:
            self.dfr_tree.selection_set(pick)
            self.dfr_tree.focus(pick)
            self.dfr_tree.see(pick)
        except Exception:
            pass
        mc = self._dfr_hits_by_iid.get(pick)
        if mc is not None:
            self._dfr_show(pick, mc)

    def _dfr_show(self, iid: str, mc, *, preserve_eth: bool = False) -> None:
        self._dfr_selected_iid = iid
        rec = dict(mc.record or {})
        name = (
            f"{rec.get('first_name') or ''} {rec.get('middle_name') or ''} "
            f"{rec.get('last_name') or ''}"
        ).strip() or (rec.get("full_name") or "—")
        name = " ".join(name.split())
        state = _format_state_display(rec)
        race = _format_race_display(mc.expected_race) or (mc.expected_race or "—")
        df = rec.get("_deepface") or {}
        face = df.get("predicted_label") or df.get("top_label") or "—"
        conf = float(mc.confidence or 0)
        sev = df.get("severity") or ""
        reason = df.get("reason") or ""
        eth_cur = self._dfr_current_ethnicity(mc)
        crime = ""
        for key in ("crime", "offense_description", "offense_type"):
            if rec.get(key):
                crime = str(rec.get(key)).strip()
                break

        photo_raw = (rec.get("photo_path") or "").strip()
        photo_path = self._dfr_resolve_photo_path(photo_raw)
        html_raw = (rec.get("report_html_path") or "").strip()
        html_path = self._dfr_resolve_existing_path(html_raw)
        raw_url = (rec.get("source_url") or "").strip()
        try:
            from scraper.public_links import openable_url_for_record

            url = openable_url_for_record(rec) or raw_url
        except Exception:
            url = raw_url

        lines = [
            f"LISTED AS: {race}",
            f"Face: {face} @ {conf:.0%}{(' · ' + sev) if sev else ''}",
            f"Ethnicity: {eth_cur}",
            f"State: {state}  ·  ID: {rec.get('id') or '—'}",
        ]
        if df.get("scanned_at"):
            lines.append(f"Scanned: {df.get('scanned_at')}")
        if crime:
            lines.append(f"Crime: {crime[:200]}")
        if reason:
            lines.append(str(reason)[:220])
        if html_path:
            lines.append(f"HTML: {html_path}")
        elif html_raw:
            lines.append(f"HTML missing: {html_raw}")
        else:
            lines.append("HTML: —")
        lines.append(f"URL: {url or '—'}")
        if photo_path:
            lines.append(f"Photo: {photo_path}")
        elif photo_raw:
            lines.append(f"Photo missing: {photo_raw}")
        else:
            lines.append("Photo: (no path on record)")

        self._dfr_html_path = html_path
        self._dfr_source_url = url or ""
        self._dfr_photo_open_path = photo_path
        self._dfr_fill_review_ui(
            name, lines, html_path, url, photo_path, photo_raw, mc, preserve_eth
        )
