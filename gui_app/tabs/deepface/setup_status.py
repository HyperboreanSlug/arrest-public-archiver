"""DeepFace setup status refresh and download badges."""
from __future__ import annotations

import importlib.util
import os
import threading
from pathlib import Path
from typing import Dict, Optional

from gui_app.theme import C


class DeepfaceSetupStatusMixin:
    def _deepface_refresh_status(self) -> None:
        """Update status labels. Keras/TF probe runs off the UI thread."""
        if not hasattr(self, "df_status_installed"):
            return
        if getattr(self, "_df_status_busy", False):
            return
        self._df_status_busy = True

        try:
            pkg = importlib.util.find_spec("deepface") is not None
        except Exception:
            pkg = False

        try:
            self.df_status_installed.configure(
                text=(
                    "Installed: package found — checking runtime…"
                    if pkg
                    else "Installed: No"
                ),
                text_color=C["accent"] if pkg else C["danger"],
            )
            self.df_status_backend.configure(
                text="Preferred backend: checking…",
                text_color=C["dim"],
            )
            self.df_status_backends.configure(text="Available: …")
        except Exception:
            pass

        home = Path.home() / ".deepface" / "weights"
        try:
            if home.is_dir():
                files = [f for f in home.glob("*") if f.is_file()]
                n = len(files)
                size = sum(f.stat().st_size for f in files)
                mb = size / (1024 * 1024)
                self.df_status_weights.configure(
                    text=f"Weights cache: {home}  ·  {n} files  ·  {mb:.1f} MB"
                )
            else:
                self.df_status_weights.configure(
                    text=f"Weights cache: not created yet ({home})"
                )
        except Exception:
            try:
                self.df_status_weights.configure(text=f"Weights cache: {home}")
            except Exception:
                pass

        skip = os.environ.get("SOR_SKIP_DEEPFACE_INSTALL", "").strip().lower() in (
            "1", "true", "yes",
        )
        if skip and hasattr(self, "df_job_status"):
            try:
                self.df_job_status.configure(
                    text="Note: SOR_SKIP_DEEPFACE_INSTALL is set — auto-install disabled in env"
                )
            except Exception:
                pass

        def worker() -> None:
            runtime_ok = False
            runtime_detail = "check failed"
            backends: Dict[str, bool] = {}
            err: Optional[str] = None
            try:
                from scraper.mugshot_ethnicity.setup import deepface_runtime_ok
                from scraper.mugshot_ethnicity.scorer import get_available_backends

                runtime_ok, runtime_detail = deepface_runtime_ok()
                backends = get_available_backends()
            except Exception as e:
                err = str(e)

            def apply() -> None:
                self._df_status_busy = False
                self._deepface_apply_status(pkg, runtime_ok, runtime_detail, backends, err)

            try:
                self.after(0, apply)
            except Exception:
                self._df_status_busy = False

        threading.Thread(
            target=worker, name="deepface-status", daemon=True
        ).start()

    def _deepface_apply_status(
        self, pkg, runtime_ok, runtime_detail, backends, err
    ) -> None:
        if not hasattr(self, "df_status_installed"):
            return
        try:
            if err:
                self.df_status_installed.configure(
                    text=f"Installed: error ({err})",
                    text_color=C["danger"],
                )
                return
            if runtime_ok:
                inst_txt = "Installed: Yes (runtime OK)"
                inst_col = C["success"]
            elif pkg:
                inst_txt = (
                    f"Installed: package present but broken — {runtime_detail}"
                )
                inst_col = C["danger"]
            else:
                inst_txt = "Installed: No"
                inst_col = C["danger"]
            self.df_status_installed.configure(text=inst_txt, text_color=inst_col)
            if runtime_ok and backends.get("deepface"):
                be = "deepface (ready)"
                col = C["success"]
            elif backends.get("clip"):
                be = "clip (fallback)"
                col = C["accent"]
            else:
                be = "none — install / repair required for mugshot tools"
                col = C["danger"]
            self.df_status_backend.configure(
                text=f"Preferred backend: {be}", text_color=col
            )
            parts = [
                f"{k}={'yes' if v else 'no'}"
                for k, v in sorted(backends.items())
            ]
            self.df_status_backends.configure(
                text="Available: " + ", ".join(parts)
            )
            try:
                self._deepface_refresh_download_badges()
            except Exception:
                pass
        except Exception:
            pass

    def _deepface_refresh_download_badges(self) -> None:
        """Update per-weight / detector “Downloaded” badges from the local cache."""
        try:
            from scraper.mugshot_ethnicity.weights_catalog import (
                DETECTOR_OPTIONS,
                detector_dropdown_label,
                detector_local_status,
                weight_local_status,
            )
        except Exception:
            return

        for mid, lbl in list(getattr(self, "_df_weight_status_labels", {}).items()):
            try:
                st = weight_local_status(mid)
                ok = bool(st.get("downloaded"))
                text = st.get("label") or ("Downloaded" if ok else "Not downloaded")
                lbl.configure(
                    text=("✓ " + text) if ok else text,
                    text_color=C["success"] if ok else C["danger"],
                )
            except Exception:
                pass

        det = self._deepface_selected_detector_id()
        try:
            det_labels = [detector_dropdown_label(d) for d in DETECTOR_OPTIONS]
            det_id_by_label = {
                detector_dropdown_label(d): d["id"] for d in DETECTOR_OPTIONS
            }
            label_by_det_id = {
                d["id"]: detector_dropdown_label(d) for d in DETECTOR_OPTIONS
            }
            self._df_det_id_by_label = det_id_by_label
            self._df_label_by_det_id = label_by_det_id
            new_label = label_by_det_id.get(det, det_labels[0] if det_labels else "")
            if hasattr(self, "df_detector_combo"):
                self.df_detector_combo.configure(values=det_labels)
            if hasattr(self, "df_detector_var") and new_label:
                self.df_detector_var.set(new_label)
            st = detector_local_status(det)
            if hasattr(self, "df_detector_status"):
                self.df_detector_status.configure(
                    text=st.get("label") or "",
                    text_color=C["success"] if st.get("downloaded") else C["danger"],
                )
        except Exception:
            pass
