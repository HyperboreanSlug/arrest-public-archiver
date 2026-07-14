"""Scan live preview and hit review pane population."""
from __future__ import annotations

from typing import Optional

from gui_app.theme import C


class DeepfaceScanLiveMixin:
    def _deepface_scan_show_live(
        self,
        rec: dict,
        done: int,
        total: int,
        *,
        face=None,
        is_hit: Optional[bool] = None,
        phase: str = "scoring",
    ) -> None:
        """Update review pane with the mugshot currently being scored (live)."""
        if not getattr(self, "_df_scan_live_preview", True):
            return
        if not hasattr(self, "df_scan_photo_lbl"):
            return
        rec = rec or {}
        name = (
            f"{rec.get('first_name') or ''} {rec.get('last_name') or ''}"
        ).strip() or (rec.get("full_name") or "—")
        state = rec.get("state") or rec.get("source_state") or "—"
        race = rec.get("race") or "—"
        photo_raw = (rec.get("photo_path") or "").strip()
        photo_path = self._deepface_scan_resolve_photo(photo_raw)

        meta_lines = [
            f"● LIVE  {done:,} / {total:,}",
            f"LISTED AS: {race}",
            f"State: {state}  ·  ID: {rec.get('id') or '—'}",
        ]
        if phase == "scoring":
            meta_lines.append("Scoring face…")
        elif face is not None:
            lab = getattr(face, "top_label", None) or "—"
            conf = float(getattr(face, "top_confidence", 0) or 0)
            err = getattr(face, "error", None)
            if err:
                meta_lines.append(f"Result: skip — {str(err)[:120]}")
            elif getattr(face, "ok", False):
                tag = "HIT" if is_hit else "ok"
                meta_lines.append(f"Face: {lab} @ {conf:.0%}  ({tag})")
            else:
                meta_lines.append("Result: no face / unknown")
        try:
            from scraper.mugshot_ethnicity.photo_quality import placeholder_reason

            if photo_path:
                stub = placeholder_reason(photo_path)
                if stub:
                    meta_lines.append(f"⚠ PLACEHOLDER: {stub}")
        except Exception:
            pass

        try:
            self.df_scan_review_name.configure(text=name)
            self.df_scan_review_meta.configure(text="\n".join(meta_lines))
            self.df_scan_review_verdict.configure(
                text="○ Live scan — click a hit to pin for review",
                text_color=C["accent"] if is_hit else C["dim"],
            )
            for bname in (
                "df_scan_btn_confirm",
                "df_scan_btn_correct",
                "df_scan_btn_skip",
            ):
                w = getattr(self, bname, None)
                if w is not None:
                    w.configure(state="disabled")
        except Exception:
            pass
        self._deepface_scan_set_photo(photo_path)
        self._df_scan_selected_iid = None

    def _deepface_scan_show_hit(self, iid: str, hit) -> None:
        """Populate review pane for one hit (mugshot + actions). Pins away from live."""
        self._df_scan_live_preview = False
        self._df_scan_selected_iid = iid
        rec = getattr(hit, "record", None) or {}
        name = (
            f"{rec.get('first_name') or ''} {rec.get('last_name') or ''}"
        ).strip() or (rec.get("full_name") or "—")
        state = rec.get("state") or rec.get("source_state") or "—"
        race = getattr(hit, "recorded_race", None) or rec.get("race") or "—"
        face = getattr(hit, "predicted_label", None) or "—"
        conf = float(getattr(hit, "confidence", 0) or 0)
        sev = getattr(hit, "severity", None) or ""
        reason = getattr(hit, "reason", None) or ""
        crime = ""
        for key in ("crime", "offense_description", "offense_type"):
            if rec.get(key):
                crime = str(rec.get(key)).strip()
                break
        meta_lines = [
            f"LISTED AS: {race}",
            f"Face: {face} @ {conf:.0%}{(' · ' + sev) if sev else ''}",
            f"State: {state}  ·  ID: {rec.get('id') or '—'}",
        ]
        if crime:
            meta_lines.append(f"Crime: {crime[:180]}")
        if reason:
            meta_lines.append(reason[:200])
        try:
            self.df_scan_review_name.configure(text=name)
            self.df_scan_review_meta.configure(text="\n".join(meta_lines))
        except Exception:
            pass

        photo_path_raw = (rec.get("photo_path") or "").strip()
        if not photo_path_raw and getattr(hit, "face", None) is not None:
            photo_path_raw = (getattr(hit.face, "photo_path", None) or "").strip()
        photo_path = self._deepface_scan_resolve_photo(photo_path_raw)
        stub_reason = None
        if photo_path is not None:
            try:
                from scraper.mugshot_ethnicity.photo_quality import placeholder_reason

                stub_reason = placeholder_reason(photo_path)
            except Exception:
                stub_reason = None
        shown = self._deepface_scan_set_photo(photo_path)
        if stub_reason:
            meta_lines.append(f"⚠ PLACEHOLDER: {stub_reason}")
            meta_lines.append("Not a real mugshot — skip / do not confirm as a hit.")
            try:
                self.df_scan_review_meta.configure(text="\n".join(meta_lines))
            except Exception:
                pass
        if not shown and photo_path is None:
            try:
                self.df_scan_photo_lbl.configure(image=None, text="No photo\non disk")
            except Exception:
                pass

        verdict = self._deepface_scan_get_verdict(hit)
        vcolor = {
            "confirmed": C["danger"], "correct": C["success"],
            "skip": C["dim"], "unreviewed": C["muted"],
        }.get(verdict, C["muted"])
        vtxt = {
            "confirmed": "● Confirmed incorrect", "correct": "● Confirmed correct",
            "skip": "● Skipped", "unreviewed": "○ Unconfirmed — choose below",
        }.get(verdict, "○ Unconfirmed")
        try:
            self.df_scan_review_verdict.configure(text=vtxt, text_color=vcolor)
            for bname in (
                "df_scan_btn_confirm", "df_scan_btn_correct", "df_scan_btn_skip",
            ):
                w = getattr(self, bname, None)
                if w is not None:
                    w.configure(state="normal")
        except Exception:
            pass
