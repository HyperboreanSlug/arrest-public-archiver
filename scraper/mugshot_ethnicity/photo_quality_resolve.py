"""Resolve mugshot paths against cwd and project roots."""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence, Union


def resolve_photo_path(
    raw: Union[str, Path, None],
    *,
    extra_roots: Optional[Sequence[Union[str, Path]]] = None,
) -> Optional[Path]:
    s = str(raw or "").strip()
    if not s:
        return None
    roots: list[Path] = [Path.cwd()]
    for root in extra_roots or ():
        try:
            roots.append(Path(root))
        except (TypeError, ValueError):
            continue
    try:
        roots.append(Path(__file__).resolve().parents[2])
    except (IndexError, OSError):
        pass
    seen: set[str] = set()
    candidates: list[Path] = []
    for base in roots:
        for variant in (s, s.replace("\\", "/"), s.replace("/", "\\")):
            for p in (Path(variant), base / variant, base / variant.replace("\\", "/")):
                key = str(p)
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(p)
    name = Path(s).name
    if name and name != s:
        for base in roots:
            candidates.append(base / "data" / "photos" / name)
            candidates.append(base / "data" / "photos" / "recentlybooked" / name)
    for p in candidates:
        try:
            if p.is_file() and p.stat().st_size > 0:
                return p.resolve()
        except OSError:
            continue
    return None
