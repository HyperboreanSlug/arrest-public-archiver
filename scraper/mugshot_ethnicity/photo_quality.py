"""Detect non-mugshot assets: registry silhouettes, 1×1 spacers, seals, banners.

Colorado (and some other SORs) often serve a white-background black-line
silhouette JPEG when no photo is on file. State HTML pages also embed seals,
skip-navigation spacers, and site chrome that must never become photo_path
or waste disk in ``*_assets/``.
"""
from __future__ import annotations

from scraper.mugshot_ethnicity.photo_quality_api import (
    bytes_non_mugshot_reason,
    clear_placeholder_cache,
    is_non_mugshot,
    is_placeholder_photo,
    non_mugshot_reason,
    placeholder_reason,
    record_has_real_photo,
    resolve_photo_path,
)
from scraper.mugshot_ethnicity.photo_quality_hashes import (
    KNOWN_CHROME_MD5,
    KNOWN_PLACEHOLDER_MD5,
    file_md5,
    is_placeholder_photo_url,
    md5_bytes,
    url_looks_like_chrome,
)
from scraper.mugshot_ethnicity.photo_quality_heuristics import (
    geometry_reason as _geometry_reason,
    heuristic_crimewatch_stock as _heuristic_crimewatch_stock,
    heuristic_crimewatch_stock_from_rgb as _heuristic_crimewatch_stock_from_rgb,
    heuristic_silhouette as _heuristic_silhouette,
    image_dims as _image_dims,
    dims_from_bytes as _dims_from_bytes,
    rgb_arrays_from_image as _rgb_arrays_from_image,
)

__all__ = [
    "KNOWN_PLACEHOLDER_MD5",
    "KNOWN_CHROME_MD5",
    "file_md5",
    "md5_bytes",
    "url_looks_like_chrome",
    "is_placeholder_photo_url",
    "record_has_real_photo",
    "non_mugshot_reason",
    "is_non_mugshot",
    "placeholder_reason",
    "is_placeholder_photo",
    "bytes_non_mugshot_reason",
    "clear_placeholder_cache",
    "resolve_photo_path",
    "_geometry_reason",
    "_heuristic_crimewatch_stock",
    "_heuristic_crimewatch_stock_from_rgb",
    "_heuristic_silhouette",
    "_image_dims",
    "_dims_from_bytes",
    "_rgb_arrays_from_image",
]
