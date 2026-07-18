"""Download one NC DAC OPI offender photo; reject placeholders."""
from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Optional, Tuple

import requests

from scraper.config_types import REQUEST_TIMEOUT, USER_AGENT
from scraper.mugshot_ethnicity.photo_quality import (
    bytes_non_mugshot_reason,
    is_placeholder_photo,
)
from scraper.nc_dac.opi_urls import detail_url, normalize_doc, picture_url

# Known OPI "No Photo Available" (also in KNOWN_PLACEHOLDER_MD5)
_OPI_NO_PHOTO_MD5 = "6685ef65a645d9bff9909240dbdb0644"
_MIN_REAL_BYTES = 5500


def photo_dest(doc: str, output_root: Path | str = Path("data/photos/nc_dac")) -> Path:
    d = normalize_doc(doc) or "unknown"
    return Path(output_root) / f"{d}.jpg"


class OpiPhotoClient:
    """Polite single-session client for OPI mugshots."""

    def __init__(self, *, delay: float = 0.75, timeout: float = REQUEST_TIMEOUT):
        self.delay = max(0.0, float(delay))
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "image/jpeg,image/*;q=0.9,*/*;q=0.5",
            }
        )
        self._last = 0.0

    def close(self) -> None:
        try:
            self.session.close()
        except Exception:
            pass

    def _throttle(self) -> None:
        if self.delay <= 0:
            return
        gap = self.delay - (time.monotonic() - self._last)
        if gap > 0:
            time.sleep(gap)

    def fetch_bytes(self, doc: str) -> Tuple[Optional[bytes], str]:
        """
        Return (jpeg_bytes, reason).
        reason is '' on success, else a short skip/error code.
        """
        d = normalize_doc(doc)
        if not d:
            return None, "no_doc"
        url = picture_url(d)
        ref = detail_url(d)
        self._throttle()
        try:
            resp = self.session.get(
                url,
                timeout=self.timeout,
                headers={"Referer": ref},
            )
            self._last = time.monotonic()
            resp.raise_for_status()
        except requests.RequestException:
            self._last = time.monotonic()
            return None, "http_error"
        data = resp.content or b""
        if len(data) < 100:
            return None, "empty"
        digest = hashlib.md5(data).hexdigest()
        if digest == _OPI_NO_PHOTO_MD5:
            return None, "no_photo"
        if len(data) < _MIN_REAL_BYTES and digest:
            # Tiny tiles are almost always stubs
            return None, "too_small"
        reason = bytes_non_mugshot_reason(data, url=url, ext=".jpg")
        if reason:
            return None, reason
        if not data.startswith(b"\xff\xd8"):
            return None, "not_jpeg"
        return data, ""

    def download(
        self,
        doc: str,
        *,
        output_root: Path | str = Path("data/photos/nc_dac"),
        force: bool = False,
    ) -> Tuple[Optional[Path], str]:
        """Save photo to disk. Returns (path, reason)."""
        d = normalize_doc(doc)
        if not d:
            return None, "no_doc"
        dest = photo_dest(d, output_root)
        if dest.is_file() and not force and not is_placeholder_photo(dest):
            return dest, "cached"
        data, reason = self.fetch_bytes(d)
        if not data:
            return None, reason or "failed"
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(".jpg.partial")
        tmp.write_bytes(data)
        tmp.replace(dest)
        if is_placeholder_photo(dest):
            try:
                dest.unlink()
            except OSError:
                pass
            return None, "placeholder"
        return dest, "ok"
