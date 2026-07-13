"""Inline record preview sidebar (photo + key fields)."""

from __future__ import annotations

import io
import threading
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import customtkinter as ctk
import requests

from gui_app.theme import C, FONT_BOLD, FONT_SM

_DETAIL_KEYS = (
    ("Name", ("full_name", "name")),
    ("Race", ("race",)),
    ("Sex", ("sex", "gender")),
    ("Age", ("age",)),
    ("State", ("state",)),
    ("County", ("county",)),
    ("Booking date", ("booking_date",)),
    ("Booking ID", ("booking_id",)),
    ("Facility", ("facility",)),
    ("Agency", ("agency",)),
    ("Charges", ("charge_description",)),
    ("Height", ("height",)),
    ("Weight", ("weight",)),
    ("Hair", ("hair",)),
    ("Eyes", ("eyes",)),
    ("Source URL", ("source_url",)),
    ("Photo path", ("photo_path",)),
)


def _first(record: Dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return str(value)
    return "—"


class RecordSidebar:
    """Right-hand photo + details pane bound to a tree selection."""

    def __init__(self, parent: Any, *, photo_size: tuple[int, int] = (240, 240)) -> None:
        self.photo_size = photo_size
        self.frame = ctk.CTkFrame(parent, fg_color=C["panel"], width=300, corner_radius=10)
        self.frame.pack_propagate(False)

        ctk.CTkLabel(
            self.frame, text="Details", font=FONT_BOLD, text_color=C["text"]
        ).pack(anchor="w", padx=12, pady=(12, 4))

        self.photo = ctk.CTkLabel(
            self.frame,
            text="Select a record",
            text_color=C["muted"],
            width=photo_size[0],
            height=photo_size[1],
            fg_color=C["elevated"],
            corner_radius=8,
        )
        self.photo.pack(padx=12, pady=8)

        self.details = ctk.CTkTextbox(
            self.frame,
            fg_color=C["bg"],
            text_color=C["text"],
            font=FONT_SM,
            wrap="word",
            activate_scrollbars=True,
        )
        self.details.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.details.insert("end", "Select a row to preview mugshot and booking fields.")
        self.details.configure(state="disabled")

        self._image_ref: Any = None
        self._load_token = 0
        self._after: Optional[Callable[..., Any]] = None

    def bind_after(self, after_fn: Callable[..., Any]) -> None:
        """Provide the host window's ``after`` for thread-safe UI updates."""
        self._after = after_fn

    def clear(self, message: str = "Select a record") -> None:
        self._load_token += 1
        self._image_ref = None
        self.photo.configure(image=None, text=message)
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("end", message)
        self.details.configure(state="disabled")

    def show(self, record: Optional[Dict[str, Any]]) -> None:
        if not record:
            self.clear()
            return
        self._load_token += 1
        token = self._load_token
        self._fill_text(record)
        self._load_photo(record, token)

    def _fill_text(self, record: Dict[str, Any]) -> None:
        lines = []
        for label, keys in _DETAIL_KEYS:
            value = _first(record, keys)
            if value != "—":
                lines.append(f"{label}: {value}")
        err = record.get("scrape_error")
        if err:
            lines.append(f"Error: {err}")
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("end", "\n".join(lines) or "No fields.")
        self.details.configure(state="disabled")

    def _set_photo(self, image: Any, text: str = "") -> None:
        self._image_ref = image
        if image is None:
            self.photo.configure(image=None, text=text or "No photo")
        else:
            self.photo.configure(image=image, text="")

    def _load_photo(self, record: Dict[str, Any], token: int) -> None:
        path = Path(str(record.get("photo_path") or ""))
        url = str(record.get("photo_url") or "").strip()
        self._set_photo(None, "Loading photo…")

        def work() -> None:
            image = None
            message = "No photo"
            try:
                from PIL import Image

                if path.is_file():
                    img = Image.open(path)
                    img = img.convert("RGB")
                    img.thumbnail(self.photo_size)
                    image = ctk.CTkImage(
                        light_image=img, dark_image=img, size=img.size
                    )
                elif url and not url.endswith("mugshot-placeholder.webp"):
                    resp = requests.get(url, timeout=20)
                    resp.raise_for_status()
                    img = Image.open(io.BytesIO(resp.content)).convert("RGB")
                    img.thumbnail(self.photo_size)
                    image = ctk.CTkImage(
                        light_image=img, dark_image=img, size=img.size
                    )
                elif url:
                    message = "Placeholder / no mugshot"
            except Exception as exc:
                message = f"Photo unavailable ({type(exc).__name__})"

            def apply() -> None:
                if token != self._load_token:
                    return
                self._set_photo(image, message)

            if self._after:
                self._after(0, apply)
            else:
                apply()

        threading.Thread(target=work, daemon=True).start()
