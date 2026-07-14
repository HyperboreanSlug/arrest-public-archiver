"""Browse → DeepFace Reports: mugshot path resolution and canvas paint."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from gui_app.theme import C
from gui_app.paths import ROOT


class DeepfaceReportsPhotoMixin:
    """Photo resolve + Canvas rendering for the review pane."""

    @staticmethod
    def _dfr_resolve_photo_path(raw: Optional[str]) -> Optional[Path]:
        """Resolve relative mugshot paths against project ROOT and cwd."""
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
        name = Path(s).name
        if name and name != s:
            candidates.append(ROOT / "data" / "report_pages" / name)
        for p in candidates:
            try:
                if p.is_file() and p.stat().st_size > 0:
                    return p.resolve()
            except OSError:
                continue
        return None

    def _dfr_set_photo_placeholder(self, text: str = "Select a hit") -> None:
        try:
            self._dfr_photo_tk = None
            cv = getattr(self, "dfr_photo_canvas", None)
            if cv is None:
                return
            cv.delete("all")
            cv.create_text(
                int(cv.cget("width") or 360) // 2,
                int(cv.cget("height") or 300) // 2,
                text=text,
                fill=C["dim"],
                font=("Segoe UI", 11),
                tags=("placeholder",),
                width=int(cv.cget("width") or 360) - 20,
                justify="center",
            )
        except Exception:
            pass

    def _dfr_set_photo_image(self, path: Path) -> tuple[bool, str]:
        """Paint mugshot onto the review Canvas. Returns (ok, message)."""
        try:
            from PIL import Image, ImageTk
        except Exception as e:
            return False, f"PIL missing: {e}"

        cv = getattr(self, "dfr_photo_canvas", None)
        if cv is None:
            return False, "photo canvas missing"

        try:
            with Image.open(path) as raw:
                img = raw.convert("RGB")
            max_w = int(getattr(self, "_DFR_PHOTO_W", 360) or 360)
            max_h = int(getattr(self, "_DFR_PHOTO_H", 300) or 300)
            img.thumbnail((max_w - 8, max_h - 8))
            w, h = img.size
            if w < 140 or h < 140:
                scale = max(140 / max(w, 1), 140 / max(h, 1))
                w = min(max_w - 8, max(1, int(w * scale)))
                h = min(max_h - 8, max(1, int(h * scale)))
                try:
                    resample = Image.Resampling.BILINEAR
                except AttributeError:
                    resample = Image.BILINEAR  # type: ignore[attr-defined]
                img = img.resize((w, h), resample)
            img = img.copy()

            try:
                master = cv.winfo_toplevel()
            except Exception:
                master = cv
            photo = ImageTk.PhotoImage(img, master=master)
            self._dfr_photo_tk = photo
            if not hasattr(self, "_dfr_image_refs") or self._dfr_image_refs is None:
                self._dfr_image_refs = []
            self._dfr_image_refs.append(photo)

            cv.delete("all")
            cv.create_image(
                max_w // 2,
                max_h // 2,
                image=photo,
                anchor="center",
                tags=("mugshot",),
            )
            cv.image = photo  # type: ignore[attr-defined]
            try:
                cv.update_idletasks()
            except Exception:
                pass
            return True, f"{path.name} ({w}x{h})"
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"
