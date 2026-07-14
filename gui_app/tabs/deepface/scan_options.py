"""Scan options collect/save, db stats, busy/stop/clear, scan log queue."""
from __future__ import annotations

import queue
from datetime import datetime
from typing import Any, Dict

from gui_app.theme import C


class DeepfaceScanOptionsMixin:
    def _deepface_goto_setup(self) -> None:
        try:
            self.deepface_tabs.set("Setup")
            if hasattr(self, "_deepface_lazy"):
                self._deepface_lazy.ensure("Setup")
        except Exception:
            pass

    def _deepface_scan_log_msg(self, msg: str) -> None:
        try:
            self._df_scan_log_queue.put(str(msg))
        except Exception:
            pass

    def _deepface_poll_scan_log(self) -> None:
        if not hasattr(self, "df_scan_log"):
            return
        try:
            while True:
                msg = self._df_scan_log_queue.get_nowait()
                self.df_scan_log.configure(state="normal")
                ts = datetime.now().strftime("%H:%M:%S")
                self.df_scan_log.insert("end", f"[{ts}] {msg}\n")
                self.df_scan_log.see("end")
                self.df_scan_log.configure(state="disabled")
        except queue.Empty:
            pass
        except Exception:
            pass
        try:
            self.after(200, self._deepface_poll_scan_log)
        except Exception:
            pass

    def _deepface_scan_collect_options(self) -> Dict[str, Any]:
        def _f(entry, default=""):
            try:
                return (entry.get() or "").strip() or default
            except Exception:
                return default

        try:
            min_conf = float(_f(self.df_scan_min_conf, "0.75") or "0.75")
        except ValueError:
            min_conf = 0.75
        try:
            limit = int(float(_f(self.df_scan_limit, "0") or "0"))
        except ValueError:
            limit = 0
        recorded = []
        for key, var in getattr(self, "_df_scan_race_vars", {}).items():
            try:
                if bool(var.get()):
                    recorded.append(key)
            except Exception:
                pass
        if not recorded:
            recorded = ["WHITE"]
        faces = []
        for key, var in getattr(self, "_df_scan_face_vars", {}).items():
            try:
                if bool(var.get()):
                    faces.append(key)
            except Exception:
                pass
        if not faces:
            faces = ["black", "indian", "asian"]
        state = _f(self.df_scan_state, "") or None
        source = _f(getattr(self, "df_scan_source", None), "") or None
        force = False
        try:
            force = bool(self.df_scan_rescan.get())
        except Exception:
            force = False
        return {
            "min_confidence": min_conf,
            "limit": max(0, limit),
            "recorded_races": recorded,
            "face_labels": faces,
            "state": state,
            "source_system": source,
            "force_rescan": force,
        }

    def _deepface_scan_refresh_db_stats(self) -> None:
        if not hasattr(self, "df_scan_db_stats"):
            return
        try:
            from scraper.database import Database

            db = Database(str(getattr(self, "db_path", None) or "data/arrests.db"))
            try:
                st = db.count_deepface_scans()
            finally:
                db.close()
            self.df_scan_db_stats.configure(
                text=f"Stored: {st.get('total', 0):,} scanned · {st.get('hits', 0):,} hits"
            )
        except Exception:
            try:
                self.df_scan_db_stats.configure(text="Stored: —")
            except Exception:
                pass

    def _deepface_scan_save_options(self) -> None:
        try:
            from scraper.app_settings import load_settings, save_settings, normalize_settings

            opts = self._deepface_scan_collect_options()
            raw = load_settings()
            raw["deepface_scan_state"] = opts["state"] or ""
            raw["deepface_scan_source"] = opts.get("source_system") or ""
            raw["deepface_scan_min_conf"] = str(opts["min_confidence"])
            raw["deepface_scan_limit"] = str(opts["limit"])
            raw["deepface_scan_recorded"] = ",".join(opts["recorded_races"])
            raw["deepface_scan_faces"] = ",".join(opts["face_labels"])
            raw["deepface_scan_force_rescan"] = bool(opts.get("force_rescan"))
            save_settings(raw)
            self.app_settings = normalize_settings(raw)
        except Exception:
            pass

    def _deepface_scan_set_busy(self, busy: bool) -> None:
        self._df_scan_running = busy
        try:
            self.df_scan_start_btn.configure(state="disabled" if busy else "normal")
            self.df_scan_stop_btn.configure(state="normal" if busy else "disabled")
        except Exception:
            pass

    def _deepface_scan_stop(self) -> None:
        self._df_scan_cancel = True
        self._deepface_scan_log_msg("Stop requested — finishing current photo…")
        try:
            self.df_scan_status.configure(
                text="Stopping…", text_color=C["accent"]
            )
        except Exception:
            pass

    def _deepface_scan_clear(self) -> None:
        self._df_scan_hits = []
        self._df_scan_hit_ids = set()
        self._df_scan_hits_by_iid = {}
        self._df_scan_selected_iid = None
        self._df_scan_image_refs = []
        try:
            self.df_scan_tree.delete(*self.df_scan_tree.get_children())
            self.df_scan_progress.set(0)
            self.df_scan_status.configure(
                text="Results cleared", text_color=C["dim"]
            )
            self._deepface_scan_clear_review()
        except Exception:
            pass
