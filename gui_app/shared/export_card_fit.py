"""Crime-panel text fitting: keep large type; grow panel, then shrink font."""
from __future__ import annotations

import re
from typing import List, Tuple

from gui_app.shared.export_card_fields import load_font
from gui_app.shared.export_card_photo import wrap_text

# Original premium card used 42pt bold with ~36px line pitch.
# Prefer that size; only step down when even a tall panel cannot fit all text.
_SIZE_STEPS: Tuple[Tuple[int, int], ...] = (
    (42, 36),
    (38, 34),
    (34, 32),
    (30, 30),
    (26, 28),
    (22, 26),
    (18, 22),
)
_DEFAULT_PANEL_H = 128
_PAD_Y = 14


def wrap_crime_text(draw, text: str, font, max_width: int) -> List[str]:
    """Wrap at middle-dot offense breaks when present."""
    text = " ".join((text or "").split())
    if not text:
        return [""]
    if not re.search(r"\s[·•]\s", text):
        return wrap_text(draw, text, font, max_width)

    parts = [p.strip() for p in re.split(r"\s*[·•]\s*", text) if p.strip()]
    if len(parts) < 2:
        return wrap_text(draw, text, font, max_width)

    lines: List[str] = []
    current = ""
    for part in parts:
        for seg in wrap_text(draw, part, font, max_width):
            if not seg:
                continue
            trial = f"{current} · {seg}" if current else seg
            if current and draw.textlength(trial, font=font) > max_width:
                lines.append(current)
                current = seg
            else:
                current = trial
    if current:
        lines.append(current)
    return lines or [""]


def plan_crime_panel(
    draw,
    text: str,
    *,
    max_width: int,
    max_height: int,
    pad_y: int = _PAD_Y,
    min_panel_h: int = _DEFAULT_PANEL_H,
) -> Tuple[object, int, List[str], int]:
    """Return (font, line_h, lines, panel_h).

    Strategy (keep original large type when possible):
    1. Try 42pt first and grow the panel up to *max_height*.
    2. Only shrink font if all text still cannot fit at *max_height*.
    Panel height is never below *min_panel_h* (original 128px box).
    """
    body = " ".join((text or "").split()) or "—"
    ceiling = max(min_panel_h, max_height)
    best = None

    for size, line_h in _SIZE_STEPS:
        font = load_font(size, bold=True)
        lines = wrap_crime_text(draw, body, font, max_width)
        if not lines:
            lines = ["—"]
        need = pad_y * 2 + len(lines) * line_h
        panel_h = max(min_panel_h, need)
        best = (font, line_h, lines, need)
        if panel_h <= ceiling:
            return font, line_h, lines, min(panel_h, ceiling)

    # Last resort: smallest size, clamp to ceiling (may be tight).
    font, line_h, lines, need = best  # type: ignore[misc]
    return font, line_h, lines, ceiling


def min_crime_panel_height(draw, text: str, max_width: int) -> int:
    """Panel height that can show *text* at preferred sizes."""
    _, _, _, h = plan_crime_panel(
        draw, text, max_width=max_width, max_height=400, pad_y=_PAD_Y
    )
    return max(_DEFAULT_PANEL_H, min(h, 360))
