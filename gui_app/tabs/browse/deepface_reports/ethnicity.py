"""Browse → DeepFace Reports: ethnicity combo + view-as-grid handoff."""
from __future__ import annotations

from tkinter import messagebox


class DeepfaceReportsEthnicityMixin:
    """Ethnicity persistence and Reports grid navigation."""

    def _dfr_current_ethnicity(self, mc) -> str:
        """Best ethnicity label for the combo (saved, then face, then Unknown)."""
        rec = getattr(mc, "record", None) or {}
        eth = (getattr(mc, "likely_ethnicity", None) or "").strip()
        if not eth or eth in ("—", "-"):
            eth = (rec.get("likely_ethnicity") or "").strip()
        if eth and eth not in ("—", "-", "unknown"):
            return eth
        df = rec.get("_deepface") or {}
        face = (df.get("predicted_label") or df.get("top_label") or "").strip()
        if face:
            face_l = face.lower().replace("_", " ")
            if "black" in face_l or "african" in face_l:
                return "African American"
            if "indian" in face_l:
                return "Indian"
            if "asian" in face_l:
                return "Asian"
            if "hispanic" in face_l or "latino" in face_l:
                return "Hispanic"
            if "white" in face_l:
                return "European"
            if "middle" in face_l or "arab" in face_l:
                return "Arabic"
            return face.replace("_", " ").title()
        return "Unknown"

    def _dfr_on_ethnicity_change(self, choice: str = "") -> None:
        """Persist ethnicity for the selected DeepFace hit."""
        if getattr(self, "_dfr_eth_updating", False):
            return
        iid = getattr(self, "_dfr_selected_iid", None)
        mc = (getattr(self, "_dfr_hits_by_iid", {}) or {}).get(iid) if iid else None
        if mc is None:
            return
        eth = (choice or "").strip()
        if not eth and hasattr(self, "dfr_eth_var"):
            eth = (self.dfr_eth_var.get() or "").strip()
        eth = eth or "Unknown"

        if hasattr(self, "_set_ethnicity_for_mc"):
            try:
                self._set_ethnicity_for_mc(mc, eth)
            except Exception:
                self._dfr_set_ethnicity_fallback(mc, eth)
        else:
            self._dfr_set_ethnicity_fallback(mc, eth)

        try:
            self._dfr_show(iid, mc, preserve_eth=True)
        except Exception:
            pass

    def _dfr_set_ethnicity_fallback(self, mc, ethnicity: str) -> None:
        """Write likely_ethnicity when Reports mixin method is unavailable."""
        eth = (ethnicity or "").strip() or "Unknown"
        mc.likely_ethnicity = eth
        rec = mc.record if isinstance(mc.record, dict) else {}
        rec = dict(rec)
        rec["likely_ethnicity"] = eth
        mc.record = rec
        rid = rec.get("id")
        if rid is None:
            return
        try:
            from scraper.database import Database

            db = Database(str(getattr(self, "db_path", None) or "data/arrests.db"))
            try:
                db.update_arrest(int(rid), {"likely_ethnicity": eth})
            finally:
                db.close()
        except Exception:
            pass

    def _dfr_view_as_grid(self) -> None:
        """Open Browse → Reports in Grid layout with DeepFace hits enabled."""
        hits = list(getattr(self, "_dfr_hits", None) or [])
        if not hits and not getattr(self, "_dfr_all_hits", None):
            messagebox.showinfo(
                "View as grid",
                "No DeepFace hits loaded yet.\nRefresh hits first, or run DeepFace → Scan.",
            )
            return

        if hasattr(self, "_browse_lazy"):
            try:
                self._browse_lazy.ensure("Reports")
            except Exception as e:
                messagebox.showerror("View as grid", f"Could not open Reports:\n{e}")
                return

        try:
            if hasattr(self, "report_include_deepface"):
                self.report_include_deepface.set(True)
            if hasattr(self, "report_photos_only"):
                self.report_photos_only.set(True)
            if hasattr(self, "report_listed_filter"):
                self.report_listed_filter.set("All")
            if hasattr(self, "report_actual_filter"):
                self.report_actual_filter.set("All")
            if hasattr(self, "report_layout_mode"):
                self.report_layout_mode.set("Grid")
            if hasattr(self, "report_grid_view"):
                self.report_grid_view.set(True)
            if hasattr(self, "report_layout_seg"):
                try:
                    self.report_layout_seg.set("Grid")
                except Exception:
                    pass

            vmap = {
                "unreviewed": "Unconfirmed",
                "confirmed": "Confirmed incorrect",
                "correct": "Confirmed correct",
                "skip": "All",
                "all": "All",
            }
            show = vmap.get(self._dfr_show_filter_key(), "Unconfirmed")
            if hasattr(self, "report_verdict_filter"):
                self.report_verdict_filter.set(show)

            if hasattr(self, "browse_tabs"):
                self.browse_tabs.set("Reports")
        except Exception as e:
            messagebox.showerror("View as grid", str(e))
            return

        def _rebuild():
            try:
                seed = list(getattr(self, "_dfr_hits", None) or [])
                self._report_page = 0
                if seed:
                    self._report_pool = seed
                    if hasattr(self, "_reports_rebuild_cards"):
                        self._reports_rebuild_cards(refilter=False)
                    if hasattr(self, "_reports_update_metrics"):
                        try:
                            self._reports_update_metrics()
                        except Exception:
                            pass
                elif hasattr(self, "_reports_on_filter_change"):
                    self._reports_on_filter_change(show_value=show)
                elif hasattr(self, "_reports_rebuild_cards"):
                    self._reports_rebuild_cards(refilter=True)
                if hasattr(self, "report_status"):
                    n = len(getattr(self, "_report_pool", None) or [])
                    self.report_status.configure(
                        text=f"DeepFace filtered hits · Grid · {n:,} people"
                    )
                if hasattr(self, "dfr_status"):
                    self.dfr_status.configure(
                        text="Opened Browse → Reports (Grid · current DeepFace filter)"
                    )
            except Exception as e:
                messagebox.showerror("View as grid", str(e))

        self.after(60, _rebuild)
