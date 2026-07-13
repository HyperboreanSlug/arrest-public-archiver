"""Compose a shareable arrest mugshot card and save it to the Desktop."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageOps

from scraper.searcher import format_race_label

_WATERMARK = "@DoDeportations"
_SEAL_PATH = (
    Path(__file__).resolve().parents[2] / "assets" / "department_of_deportations_seal.png"
)
_CARD_W = 1080
_CARD_H = 1350
_PHOTO_H = 820
_BG = (12, 12, 14, 255)
_PANEL = (26, 26, 32, 255)
_TEXT = (236, 236, 241, 255)
_MUTED = (155, 155, 168, 255)
_ACCENT = (232, 168, 124, 255)


def _desktop_dir() -> Path:
    home = Path.home()
    for name in ("Desktop", "OneDrive/Desktop", "OneDrive/Рабочий стол"):
        candidate = home / name
        if candidate.is_dir():
            return candidate
    desktop = home / "Desktop"
    desktop.mkdir(parents=True, exist_ok=True)
    return desktop


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^\w\s\-]+", "", name, flags=re.UNICODE).strip()
    cleaned = re.sub(r"\s+", "_", cleaned) or "arrest"
    return cleaned[:80]


def _load_font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    windir = Path(os_environ_get("WINDIR", r"C:\Windows"))
    candidates = []
    if bold:
        candidates.extend(
            [
                windir / "Fonts" / "segoeuib.ttf",
                windir / "Fonts" / "arialbd.ttf",
                windir / "Fonts" / "calibrib.ttf",
            ]
        )
    candidates.extend(
        [
            windir / "Fonts" / "segoeui.ttf",
            windir / "Fonts" / "arial.ttf",
            windir / "Fonts" / "calibri.ttf",
        ]
    )
    for path in candidates:
        try:
            if path.is_file():
                return ImageFont.truetype(str(path), size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def os_environ_get(key: str, default: str = "") -> str:
    import os

    return os.environ.get(key, default)


def _person_name(record: Mapping[str, Any]) -> str:
    full = str(record.get("full_name") or "").strip()
    if full:
        return full
    parts = [
        str(record.get("first_name") or "").strip(),
        str(record.get("middle_name") or "").strip(),
        str(record.get("last_name") or "").strip(),
    ]
    return " ".join(p for p in parts if p) or "Unknown"


def _location(record: Mapping[str, Any]) -> str:
    county = str(record.get("county") or "").strip()
    state = str(record.get("state") or "").strip().upper()
    city = str(record.get("city") or "").strip()
    bits = []
    if city:
        bits.append(city.title())
    if county:
        c = county.replace("-", " ").replace("_", " ").title()
        if not c.lower().endswith("county"):
            c = f"{c} County"
        bits.append(c)
    if state:
        bits.append(state)
    return ", ".join(bits) or "Unknown location"


def _crime(record: Mapping[str, Any]) -> str:
    charge = str(record.get("charge_description") or "").strip()
    if charge:
        return charge
    cat = str(record.get("charge_category") or "").strip()
    return cat.replace("_", " ").title() if cat else "Unknown charge"


def _resolve_photo_path(raw: Any) -> Optional[Path]:
    text = str(raw or "").strip()
    if not text:
        return None
    path = Path(text)
    if path.is_file():
        return path
    alt = Path.cwd() / path
    if alt.is_file():
        return alt
    return path if path.exists() else None


def _load_mugshot(record: Mapping[str, Any], box: Tuple[int, int]) -> Image.Image:
    path = _resolve_photo_path(record.get("photo_path"))
    img: Optional[Image.Image] = None
    if path and path.is_file():
        try:
            img = Image.open(path)
            if getattr(img, "n_frames", 1) > 1:
                img.seek(0)
            img = img.convert("RGB")
        except Exception:
            img = None
    if img is None:
        url = str(record.get("photo_url") or "").strip()
        if url and "mugshot-placeholder" not in url.lower():
            try:
                import requests
                from scraper.config import USER_AGENT

                resp = requests.get(
                    url,
                    timeout=25,
                    headers={
                        "User-Agent": USER_AGENT,
                        "Accept": "image/webp,image/*,*/*;q=0.8",
                        "Referer": "https://recentlybooked.com/",
                    },
                )
                resp.raise_for_status()
                import io

                img = Image.open(io.BytesIO(resp.content)).convert("RGB")
            except Exception:
                img = None
    if img is None:
        placeholder = Image.new("RGB", box, (34, 34, 42))
        draw = ImageDraw.Draw(placeholder)
        font = _load_font(42, bold=True)
        msg = "NO PHOTO"
        bbox = draw.textbbox((0, 0), msg, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(
            ((box[0] - tw) / 2, (box[1] - th) / 2),
            msg,
            font=font,
            fill=(120, 120, 130),
        )
        return placeholder
    return ImageOps.fit(img, box, method=Image.Resampling.LANCZOS, centering=(0.5, 0.35))


def _wrap_text(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int
) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _with_opacity(img: Image.Image, opacity: float) -> Image.Image:
    """Multiply existing alpha by *opacity* (0..1)."""
    rgba = img.convert("RGBA")
    r, g, b, a = rgba.split()
    factor = max(0.0, min(1.0, float(opacity)))
    a = a.point(lambda p: int(round(p * factor)))
    out = Image.merge("RGBA", (r, g, b, a))
    return out


def _draw_seal_watermark(
    canvas: Image.Image,
    *,
    photo_box: Tuple[int, int, int, int],
    text: str = _WATERMARK,
    opacity: float = 0.10,
) -> None:
    """Center the Department seal on the mugshot with handle text beneath it."""
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    left, top, right, bottom = photo_box
    photo_w = max(1, right - left)
    photo_h = max(1, bottom - top)

    if _SEAL_PATH.is_file():
        seal = Image.open(_SEAL_PATH).convert("RGBA")
        # Cover most of the mugshot while leaving room for text under the seal.
        target = int(min(photo_w, photo_h) * 0.78)
        seal = seal.resize((target, target), Image.Resampling.LANCZOS)
        seal = _with_opacity(seal, opacity)
        seal_x = left + (photo_w - target) // 2
        seal_y = top + max(8, int(photo_h * 0.08))
        overlay.paste(seal, (seal_x, seal_y), seal)
        text_top = seal_y + target + 12
    else:
        text_top = top + photo_h // 2

    draw = ImageDraw.Draw(overlay)
    font = _load_font(max(36, photo_w // 14), bold=True)
    alpha = max(1, int(round(255 * opacity)))
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = left + (photo_w - tw) // 2
    ty = min(bottom - th - 16, text_top)
    draw.text((tx, ty), text, font=font, fill=(255, 255, 255, alpha))
    canvas.alpha_composite(overlay)


def render_export_card(record: Mapping[str, Any]) -> Image.Image:
    """Build an RGBA share card for *record*."""
    canvas = Image.new("RGBA", (_CARD_W, _CARD_H), _BG)
    draw = ImageDraw.Draw(canvas)

    # Photo panel
    margin = 48
    photo_box = (_CARD_W - margin * 2, _PHOTO_H)
    photo_rect = (margin, margin, margin + photo_box[0], margin + photo_box[1])
    mug = _load_mugshot(record, photo_box).convert("RGBA")
    canvas.paste(mug, (margin, margin), mug if mug.mode == "RGBA" else None)

    # Seal + @handle watermark on the mugshot at 10% opacity
    _draw_seal_watermark(canvas, photo_box=photo_rect, opacity=0.10)

    # Accent bar under photo
    bar_y = margin + _PHOTO_H + 18
    draw.rounded_rectangle(
        (margin, bar_y, _CARD_W - margin, bar_y + 8),
        radius=4,
        fill=_ACCENT,
    )

    name = _person_name(record)
    race = format_race_label(str(record.get("race") or "").strip()) or "Unknown"
    location = _location(record)
    crime = _crime(record)

    name_font = _load_font(54, bold=True)
    label_font = _load_font(26)
    value_font = _load_font(34, bold=True)

    y = bar_y + 28
    max_text_w = _CARD_W - margin * 2

    for line in _wrap_text(draw, name, name_font, max_text_w)[:2]:
        draw.text((margin, y), line, font=name_font, fill=_TEXT)
        y += 62

    def section(label: str, value: str, top: int) -> int:
        draw.text((margin, top), label.upper(), font=label_font, fill=_MUTED)
        top += 34
        for line in _wrap_text(draw, value, value_font, max_text_w)[:3]:
            draw.text((margin, top), line, font=value_font, fill=_TEXT)
            top += 42
        return top + 10

    y = section("Race marked", race, y + 8)
    y = section("Arrest location", location, y)
    y = section("Crime", crime, y)

    # Bottom-right handle at 100% opacity
    handle = _WATERMARK
    handle_font = _load_font(28, bold=True)
    hb = draw.textbbox((0, 0), handle, font=handle_font)
    hw, hh = hb[2] - hb[0], hb[3] - hb[1]
    draw.text(
        (_CARD_W - margin - hw, _CARD_H - margin - hh),
        handle,
        font=handle_font,
        fill=(255, 255, 255, 255),
    )

    return canvas


def export_record_card_to_desktop(record: Mapping[str, Any]) -> Path:
    """Render and save a PNG card to the user's Desktop; return the path."""
    img = render_export_card(record)
    desktop = _desktop_dir()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = _safe_filename(_person_name(record))
    out = desktop / f"{name}_{stamp}.png"
    # Avoid clobbering if same-second export
    n = 1
    while out.exists():
        out = desktop / f"{name}_{stamp}_{n}.png"
        n += 1
    img.convert("RGB").save(out, format="PNG", optimize=True)
    return out
