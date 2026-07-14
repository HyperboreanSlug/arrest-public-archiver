"""Scan hit verdicts, selection, navigation, and tree append."""
from __future__ import annotations

import json

from gui_app.paths import ROOT
from gui_app.theme import C


class DeepfaceScanReviewMixin:
    def _deepface_scan_verdict_key(self, hit) -> str:
        rec = getattr(hit, "record", None) or {}
        rid = rec.get("id")
        if rid is not None and str(rid).strip() != "":
            return f"id:{rid}"
        name = f"{rec.get('first_name') or ''} {rec.get('last_name') or ''}".strip()
        return f"df:{name}|{getattr(hit, 'predicted_label', '')}"

    def _deepface_scan_get_verdict(self, hit) -> str:
        if not hasattr(self, "_report_verdicts") or self._report_verdicts is None:
            self._report_verdicts = {}
            if hasattr(self, "_load_report_verdicts"):
                try:
                    self._load_report_verdicts()
                except Exception:
                    pass
        key = self._deepface_scan_verdict_key(hit)
        v = (self._report_verdicts.get(key) or "").strip()
        if v in ("confirmed", "correct", "skip"):
            return v
        rec = getattr(hit, "record", None) or {}
        rid = rec.get("id")
        if rid is not None:
            v2 = (self._report_verdicts.get(f"id:{rid}") or "").strip()
            if v2 in ("confirmed", "correct", "skip"):
                return v2
        return "unreviewed"

    def _deepface_scan_verdict_label(self, verdict: str) -> str:
        return {
            "confirmed": "Incorrect", "correct": "Correct",
            "skip": "Skip", "unreviewed": "—",
        }.get(verdict or "unreviewed", "—")

    def _deepface_scan_on_select(self, _event=None) -> None:
        if not hasattr(self, "df_scan_tree"):
            return
        try:
            sel = self.df_scan_tree.selection()
            if not sel:
                return
            iid = sel[0]
            hit = (getattr(self, "_df_scan_hits_by_iid", {}) or {}).get(iid)
            if hit is None:
                return
            self._df_scan_live_preview = False
            self._deepface_scan_show_hit(iid, hit)
        except Exception:
            pass

    def _deepface_scan_set_verdict(self, verdict: str) -> None:
        """Confirm incorrect / correct / skip for the selected hit (→ Reports)."""
        iid = getattr(self, "_df_scan_selected_iid", None)
        hit = (getattr(self, "_df_scan_hits_by_iid", {}) or {}).get(iid) if iid else None
        if hit is None:
            try:
                sel = self.df_scan_tree.selection()
                if sel:
                    iid = sel[0]
                    hit = self._df_scan_hits_by_iid.get(iid)
            except Exception:
                pass
        if hit is None:
            self._deepface_scan_log_msg("Select a hit first")
            return
        if not hasattr(self, "_report_verdicts") or self._report_verdicts is None:
            self._report_verdicts = {}
        key = self._deepface_scan_verdict_key(hit)
        keys = [key]
        rec = hit.record or {}
        rid = rec.get("id")
        if rid is not None:
            keys.append(f"id:{rid}")
        verdict = (verdict or "").strip()
        if verdict == "unreviewed":
            for k in keys:
                self._report_verdicts.pop(k, None)
        else:
            for k in keys:
                self._report_verdicts[k] = verdict
        if hasattr(self, "_save_report_verdicts"):
            try:
                self._save_report_verdicts()
            except Exception:
                try:
                    path = ROOT / "data" / "report_verdicts.json"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(
                        json.dumps(self._report_verdicts, indent=2, sort_keys=True),
                        encoding="utf-8",
                    )
                except Exception as e:
                    self._deepface_scan_log_msg(f"Could not save verdict: {e}")
                    return
        if iid and hasattr(self, "df_scan_tree"):
            try:
                vals = list(self.df_scan_tree.item(iid, "values") or [])
                if len(vals) >= 6:
                    vals[5] = self._deepface_scan_verdict_label(verdict)
                    self.df_scan_tree.item(iid, values=vals)
            except Exception:
                pass
        self._deepface_scan_show_hit(iid, hit)
        self._deepface_scan_log_msg(
            f"Verdict {verdict} → {key} "
            f"({(rec.get('first_name') or '')} {(rec.get('last_name') or '')})".strip()
        )
        self.after(50, self._deepface_scan_next_unreviewed)

    def _deepface_scan_next_unreviewed(self) -> None:
        if not hasattr(self, "df_scan_tree"):
            return
        try:
            kids = list(self.df_scan_tree.get_children() or [])
            if not kids:
                return
            start = 0
            sel = self.df_scan_tree.selection()
            if sel:
                try:
                    start = kids.index(sel[0]) + 1
                except ValueError:
                    start = 0
            order = kids[start:] + kids[:start]
            for iid in order:
                hit = (self._df_scan_hits_by_iid or {}).get(iid)
                if hit is None:
                    continue
                if self._deepface_scan_get_verdict(hit) == "unreviewed":
                    self.df_scan_tree.selection_set(iid)
                    self.df_scan_tree.focus(iid)
                    self.df_scan_tree.see(iid)
                    self._deepface_scan_show_hit(iid, hit)
                    return
            self._deepface_scan_log_msg("No unreviewed hits left")
        except Exception:
            pass

    def _deepface_scan_append_hit(self, hit) -> None:
        """Insert one hit into the results tree (main thread; live updates)."""
        if not hasattr(self, "df_scan_tree"):
            return
        try:
            rec = hit.record or {}
            try:
                oid = int(rec["id"]) if rec.get("id") is not None else None
            except (TypeError, ValueError):
                oid = None
            seen = getattr(self, "_df_scan_hit_ids", None)
            if seen is None:
                self._df_scan_hit_ids = set()
                seen = self._df_scan_hit_ids
            if oid is not None and oid in seen:
                return
            if oid is not None:
                seen.add(oid)
            name = f"{rec.get('first_name') or ''} {rec.get('last_name') or ''}".strip()
            verdict = self._deepface_scan_get_verdict(hit)
            iid = self.df_scan_tree.insert(
                "", "end",
                values=(
                    name, rec.get("state") or "—",
                    (hit.recorded_race or "—")[:20], hit.predicted_label,
                    f"{float(hit.confidence or 0):.2f}",
                    self._deepface_scan_verdict_label(verdict), rec.get("id") or "",
                ),
            )
            if not hasattr(self, "_df_scan_hits_by_iid"):
                self._df_scan_hits_by_iid = {}
            self._df_scan_hits_by_iid[iid] = hit
            try:
                self.df_scan_tree.see(iid)
            except Exception:
                pass
            if not hasattr(self, "_df_scan_hits") or self._df_scan_hits is None:
                self._df_scan_hits = []
            self._df_scan_hits.append(hit)
            n = len(self._df_scan_hits)
            try:
                self.df_scan_status.configure(text=f"Live · {n:,} hits", text_color=C["text"])
            except Exception:
                pass
        except Exception:
            pass
