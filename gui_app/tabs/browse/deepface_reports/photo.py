"""Browse → DeepFace Reports: mugshot path resolution and canvas paint."""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

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

    def _dfr_photo_box(self) -> Tuple[int, int]:
        """Live canvas size (fallback to stored defaults)."""
        cv = getattr(self, "dfr_photo_canvas", None)
        max_w = int(getattr(self, "_DFR_PHOTO_W", 360) or 360)
        max_h = int(getattr(self, "_DFR_PHOTO_H", 300) or 300)
        if cv is not None:
            try:
                cw = int(cv.winfo_width() or 0)
                ch = int(cv.winfo_height() or 0)
                if cw >= 40:
                    max_w = cw
                if ch >= 40:
                    max_h = ch
            except Exception:
                pass
        return max(40, max_w), max(40, max_h)

    def _dfr_set_photo_placeholder(self, text: str = "Select a hit") -> None:
        try:
            self._dfr_photo_tk = None
            self._dfr_photo_path = None
            cv = getattr(self, "dfr_photo_canvas", None)
            if cv is None:
                return
            cv.delete("all")
            max_w, max_h = self._dfr_photo_box()
            cv.create_text(
                max_w // 2,
                max_h // 2,
                text=text,
                fill=C["dim"],
                font=("Segoe UI", 11),
                tags=("placeholder",),
                width=max(20, max_w - 20),
                justify="center",
            )
        except Exception:
            pass

    def _dfr_bind_photo_resize(self) -> None:
        """Hook canvas configure so mugshots re-fit when the pane is resized."""
        cv = getattr(self, "dfr_photo_canvas", None)
        if cv is None or getattr(self, "_dfr_photo_resize_bound", False):
            return
        self._dfr_photo_resize_bound = True
        self._dfr_photo_resize_after = None

        def _on_cfg(_event=None) -> None:
            aid = getattr(self, "_dfr_photo_resize_after", None)
            if aid is not None:
                try:
                    cv.after_cancel(aid)
                except Exception:
                    pass
            self._dfr_photo_resize_after = cv.after(90, self._dfr_refit_photo)

        try:
            cv.bind("<Configure>", _on_cfg, add="+")
        except Exception:
            pass

    def _dfr_refit_photo(self) -> None:
        self._dfr_photo_resize_after = None
        path = getattr(self, "_dfr_photo_path", None)
        if path is None:
            return
        try:
            if Path(path).is_file():
                self._dfr_set_photo_image(Path(path))
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
            self._dfr_bind_photo_resize()
            with Image.open(path) as raw:
                img = raw.convert("RGB")
            max_w, max_h = self._dfr_photo_box()
            # Contain inside canvas with a small inset
            box = (max(16, max_w - 8), max(16, max_h - 8))
            try:
                resample = Image.Resampling.LANCZOS
            except AttributeError:
                resample = Image.LANCZOS  # type: ignore[attr-defined]
            img = img.copy()
            img.thumbnail(box, resample)
            w, h = img.size
            if w < 1 or h < 1:
                return False, "empty image"
            img = img.copy()

            try:
                master = cv.winfo_toplevel()
            except Exception:
                master = cv
            photo = ImageTk.PhotoImage(img, master=master)
            self._dfr_photo_tk = photo
            self._dfr_photo_path = path
            if not hasattr(self, "_dfr_image_refs") or self._dfr_image_refs is None:
                self._dfr_image_refs = []
            self._dfr_image_refs.append(photo)
            # Cap retained refs so resize storms don't balloon memory
            if len(self._dfr_image_refs) > 12:
                self._dfr_image_refs = self._dfr_image_refs[-8:]

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
