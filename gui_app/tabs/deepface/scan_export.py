"""DeepFace scan callbacks, finish UI, and CSV/JSON export."""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from tkinter import filedialog

from gui_app.theme import C


class DeepfaceScanExportMixin:
    def _deepface_scan_callbacks(self, live_gen: int):
        def progress(done: int, total: int) -> None:
            def ui():
                try:
                    frac = (done / total) if total else 0.0
                    self.df_scan_progress.set(min(1.0, max(0.0, frac)))
                    n = len(getattr(self, "_df_scan_hits", []) or [])
                    self.df_scan_status.configure(
                        text=f"Scoring {done:,} / {total:,}  ·  hits {n:,}",
                        text_color=C["text"],
                    )
                except Exception:
                    pass

            try:
                self.after(0, ui)
            except Exception:
                pass

        def on_photo(rec, done: int, total: int) -> None:
            def ui(r=rec, d=done, t=total, gen=live_gen):
                if gen != getattr(self, "_df_scan_live_seq", 0):
                    return
                try:
                    self._deepface_scan_show_live(r, d, t, phase="scoring")
                except Exception:
                    pass

            try:
                self.after(0, ui)
            except Exception:
                pass

        def on_scored(rec, face, is_hit: bool, done: int, total: int) -> None:
            def ui(r=rec, f=face, h=is_hit, d=done, t=total, gen=live_gen):
                if gen != getattr(self, "_df_scan_live_seq", 0):
                    return
                if not getattr(self, "_df_scan_live_preview", True):
                    return
                try:
                    self._deepface_scan_show_live(
                        r, d, t, face=f, is_hit=h, phase="scored"
                    )
                except Exception:
                    pass

            try:
                self.after(0, ui)
            except Exception:
                pass

        def on_hit(hit) -> None:
            try:
                self.after(0, lambda h=hit: self._deepface_scan_append_hit(h))
            except Exception:
                pass

        return progress, on_photo, on_scored, on_hit

    def _deepface_scan_finish(self, hits, err) -> None:
        self._deepface_scan_set_busy(False)
        if hits and not getattr(self, "_df_scan_hits", None):
            self._df_scan_hits = list(hits)
        elif hits:
            self._df_scan_hits = list(hits)
        n = len(getattr(self, "_df_scan_hits", []) or [])
        try:
            if err:
                self.df_scan_status.configure(
                    text=f"Failed: {err}", text_color=C["danger"],
                )
                self.df_scan_progress.set(0)
            elif getattr(self, "_df_scan_cancel", False):
                self.df_scan_status.configure(
                    text=f"Stopped — {n:,} hits", text_color=C["accent"],
                )
            else:
                self.df_scan_progress.set(1.0)
                self.df_scan_status.configure(
                    text=f"Done — {n:,} hits", text_color=C["success"],
                )
        except Exception:
            pass
        self._deepface_scan_log_msg(
            f"Scan finished: {n} hits"
            + (f" (error: {err})" if err else "")
            + " — results stored; skipped photos stay skipped next run"
        )
        try:
            self._deepface_scan_refresh_db_stats()
        except Exception:
            pass
        try:
            if n and getattr(self, "_df_scan_live_preview", True):
                self.after(80, self._deepface_scan_next_unreviewed)
        except Exception:
            pass

    def _deepface_scan_export(self) -> None:
        hits = list(getattr(self, "_df_scan_hits", []) or [])
        if not hits:
            self._deepface_scan_log_msg("No hits to export")
            return
        path = filedialog.asksaveasfilename(
            title="Export DeepFace scan hits",
            defaultextension=".csv",
            filetypes=[
                ("CSV", "*.csv"),
                ("JSON", "*.json"),
                ("All", "*.*"),
            ],
            initialfile=f"deepface_scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        )
        if not path:
            return
        try:
            p = Path(path)
            if p.suffix.lower() == ".json":
                p.write_text(
                    json.dumps([h.to_dict() for h in hits], indent=2),
                    encoding="utf-8",
                )
            else:
                with open(p, "w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow([
                        "id", "name", "state", "recorded_race", "predicted_label",
                        "confidence", "severity", "reason", "photo_path",
                    ])
                    for h in hits:
                        rec = h.record or {}
                        w.writerow([
                            rec.get("id"),
                            f"{rec.get('first_name') or ''} {rec.get('last_name') or ''}".strip(),
                            rec.get("state"),
                            h.recorded_race,
                            h.predicted_label,
                            f"{h.confidence:.4f}",
                            h.severity,
                            h.reason,
                            getattr(h.face, "photo_path", None),
                        ])
            self._deepface_scan_log_msg(f"Exported {len(hits)} hits → {p}")
        except Exception as e:
            self._deepface_scan_log_msg(f"Export failed: {e}")
