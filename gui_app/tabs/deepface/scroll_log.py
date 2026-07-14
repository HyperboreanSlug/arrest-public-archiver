"""DeepFace setup scroll binding, activity log, and open log/weights helpers."""
from __future__ import annotations

import os
import queue
from datetime import datetime
from pathlib import Path

from gui_app.paths import ROOT


class DeepfaceScrollLogMixin:
    def _deepface_bind_scroll_children(self, tab, scroll_frame) -> None:
        """Fast mouse-wheel scrolling over the full DeepFace tab content."""
        try:
            canvas = scroll_frame._parent_canvas  # type: ignore[attr-defined]
        except Exception:
            return

        PAGE_FRAC = 0.18

        def _scroll_by_notches(notches: int) -> None:
            if notches == 0:
                return
            try:
                first, last = canvas.yview()
            except Exception:
                canvas.yview_scroll(notches * 12, "units")
                return
            page = max(last - first, 0.05)
            step = notches * max(PAGE_FRAC * page, 0.08)
            try:
                canvas.yview_moveto(max(0.0, min(1.0, first + step)))
            except Exception:
                canvas.yview_scroll(notches * 12, "units")

        def _wheel(event):
            delta = getattr(event, "delta", 0) or 0
            if delta:
                if abs(delta) >= 120:
                    notches = int(-delta / 120)
                else:
                    notches = -1 if delta > 0 else 1
                if notches == 0:
                    notches = -1 if delta > 0 else 1
                _scroll_by_notches(notches)
            else:
                num = getattr(event, "num", 0)
                if num == 4:
                    _scroll_by_notches(-1)
                elif num == 5:
                    _scroll_by_notches(1)
            return "break"

        def _walk(w):
            try:
                if w is getattr(self, "df_log", None):
                    return
            except Exception:
                pass
            try:
                w.bind("<MouseWheel>", _wheel)
                w.bind("<Button-4>", _wheel)
                w.bind("<Button-5>", _wheel)
            except Exception:
                pass
            try:
                for child in w.winfo_children():
                    _walk(child)
            except Exception:
                pass

        try:
            _walk(tab)
            _walk(scroll_frame)
            for w in (
                tab,
                getattr(scroll_frame, "_parent_frame", None),
                canvas,
                scroll_frame,
            ):
                if w is None:
                    continue
                try:
                    w.bind("<MouseWheel>", _wheel)
                    w.bind("<Button-4>", _wheel)
                    w.bind("<Button-5>", _wheel)
                except Exception:
                    pass
        except Exception:
            pass

    def _deepface_append_log(self, msg: str) -> None:
        try:
            self._df_log_queue.put(str(msg))
        except Exception:
            pass

    def _deepface_poll_log(self) -> None:
        if not hasattr(self, "df_log"):
            return
        try:
            while True:
                msg = self._df_log_queue.get_nowait()
                self.df_log.configure(state="normal")
                ts = datetime.now().strftime("%H:%M:%S")
                self.df_log.insert("end", f"[{ts}] {msg}\n")
                self.df_log.see("end")
                self.df_log.configure(state="disabled")
        except queue.Empty:
            pass
        except Exception:
            pass
        try:
            self.after(200, self._deepface_poll_log)
        except Exception:
            pass

    def _deepface_open_log(self) -> None:
        path = ROOT / "deepface_setup.log"
        if not path.is_file():
            try:
                path.write_text("# DeepFace setup log\n", encoding="utf-8")
            except OSError:
                pass
        if hasattr(self, "_open_path"):
            self._open_path(path)
        else:
            try:
                os.startfile(str(path))  # type: ignore[attr-defined]
            except Exception:
                pass

    def _deepface_open_weights_dir(self) -> None:
        path = Path.home() / ".deepface" / "weights"
        path.mkdir(parents=True, exist_ok=True)
        if hasattr(self, "_open_path"):
            self._open_path(path)
        else:
            try:
                os.startfile(str(path))  # type: ignore[attr-defined]
            except Exception:
                pass
