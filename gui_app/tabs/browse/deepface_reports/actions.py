"""Browse → DeepFace Reports: open links, copy, verdicts, next unreviewed."""
from __future__ import annotations

import json
import os
import webbrowser

from tkinter import messagebox

from gui_app.paths import ROOT


class DeepfaceReportsActionsMixin:
    """Link openers, clipboard, verdict write, navigation."""

    def _dfr_open_html(self) -> None:
        path = getattr(self, "_dfr_html_path", None)
        if path is None or not path.is_file():
            return
        if hasattr(self, "_open_path"):
            self._open_path(path)
        else:
            try:
                if os.name == "nt":
                    os.startfile(str(path))  # type: ignore[attr-defined]
                else:
                    webbrowser.open(path.as_uri())
            except Exception as e:
                messagebox.showerror("Open HTML", str(e))

    def _dfr_open_url(self) -> None:
        url = (getattr(self, "_dfr_source_url", None) or "").strip()
        if not url:
            return
        try:
            webbrowser.open(url)
        except Exception as e:
            messagebox.showerror("Open URL", str(e))

    def _dfr_open_photo(self) -> None:
        path = getattr(self, "_dfr_photo_open_path", None)
        if path is None or not path.is_file():
            return
        if hasattr(self, "_open_path"):
            self._open_path(path)
        else:
            try:
                if os.name == "nt":
                    os.startfile(str(path))  # type: ignore[attr-defined]
                else:
                    webbrowser.open(path.as_uri())
            except Exception as e:
                messagebox.showerror("Open photo", str(e))

    def _dfr_copy_detail(self) -> None:
        text = (getattr(self, "_dfr_meta_text", None) or "").strip()
        name = ""
        try:
            name = (self.dfr_name.cget("text") or "").strip()
        except Exception:
            pass
        if name and name != "—" and not text.startswith(name):
            text = f"{name}\n{text}" if text else name
        if not text:
            return
        if hasattr(self, "_copy_to_clipboard"):
            self._copy_to_clipboard(text, toast="DeepFace detail copied")
            if hasattr(self, "dfr_status"):
                try:
                    self.dfr_status.configure(text="Copied detail to clipboard")
                except Exception:
                    pass
        else:
            try:
                self.clipboard_clear()
                self.clipboard_append(text)
            except Exception as e:
                messagebox.showerror("Copy", str(e))

    def _dfr_set_verdict(self, verdict: str) -> None:
        iid = getattr(self, "_dfr_selected_iid", None)
        mc = self._dfr_hits_by_iid.get(iid) if iid else None
        if mc is None:
            try:
                sel = self.dfr_tree.selection()
                if sel:
                    iid = sel[0]
                    mc = self._dfr_hits_by_iid.get(iid)
            except Exception:
                pass
        if mc is None:
            return

        if hasattr(self, "_set_verdict_for_mc"):
            try:
                self._set_verdict_for_mc(mc, verdict, save=True)
            except Exception:
                self._dfr_save_verdict_fallback(mc, verdict)
        else:
            self._dfr_save_verdict_fallback(mc, verdict)

        if iid and hasattr(self, "dfr_tree"):
            try:
                vals = list(self.dfr_tree.item(iid, "values") or [])
                if len(vals) >= 7:
                    vals[6] = self._dfr_verdict_label(verdict)
                    self.dfr_tree.item(iid, values=vals)
            except Exception:
                pass
        self._dfr_show(iid, mc)
        self._dfr_update_metrics()
        self.after(40, self._dfr_next_unreviewed)

    def _dfr_save_verdict_fallback(self, mc, verdict: str) -> None:
        if not hasattr(self, "_report_verdicts") or self._report_verdicts is None:
            self._report_verdicts = {}
        key = self._dfr_verdict_key_for_mc(mc)
        keys = [key]
        rid = (mc.record or {}).get("id")
        if rid is not None:
            keys.append(f"id:{rid}")
        if verdict == "unreviewed":
            for k in keys:
                self._report_verdicts.pop(k, None)
        else:
            for k in keys:
                self._report_verdicts[k] = verdict
        if hasattr(self, "_save_report_verdicts"):
            try:
                self._save_report_verdicts()
                return
            except Exception:
                pass
        path = ROOT / "data" / "report_verdicts.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self._report_verdicts, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _dfr_next_unreviewed(self) -> None:
        if not hasattr(self, "dfr_tree"):
            return
        kids = list(self.dfr_tree.get_children() or [])
        if not kids:
            return
        start = 0
        sel = self.dfr_tree.selection()
        if sel:
            try:
                start = kids.index(sel[0]) + 1
            except ValueError:
                start = 0
        order = kids[start:] + kids[:start]
        for iid in order:
            mc = self._dfr_hits_by_iid.get(iid)
            if mc is None:
                continue
            if self._dfr_get_verdict(mc) == "unreviewed":
                self.dfr_tree.selection_set(iid)
                self.dfr_tree.focus(iid)
                self.dfr_tree.see(iid)
                self._dfr_show(iid, mc)
                return
        if hasattr(self, "dfr_status"):
            self.dfr_status.configure(text="No unreviewed hits in current filter")
