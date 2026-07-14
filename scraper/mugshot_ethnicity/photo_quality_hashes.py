"""Known placeholder/chrome MD5s and basic hash/URL chrome detection."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Optional, Set, Union

# Byte-identical CO "no photo" silhouette (299×289 L JPEG, ~7.2 KB).
# RecentlyBooked default mugshot stubs (~1–2 KB webp).
KNOWN_PLACEHOLDER_MD5: Set[str] = {
    "5030072b8b5ad8f44f389eb77b3d3d70",
    "8125966493d0b36f032ae9c4d4585210",  # mugshot-placeholder.webp
    "c3786b41be8d238a5f52136bd876bfa4",  # mugshot-placeholder-female.webp
    "2344828d8440248c173c9d47c1eb13b0",  # RecentlyBooked "no photo" silhouette (303×250)
    # CrimeWatch / RecentlyBooked stock "ARREST" handcuffs tile (250×250 webp)
    "8558ffafb796af4dacd58e85145b3138",
}

# Known site-chrome / stub hashes from archive audits (not real faces).
KNOWN_CHROME_MD5: Set[str] = {
    "5241a2d8ac75f34e0373765f6249194f",  # NV 1×1 transparent GIF
    "0a668c6c65c40b293dff33a81c6849ae",  # Tiny multi-state stub 59×78
    "3085230ce03a9a93a074669e4c194432",  # KS 16×16 icon
    "cfe6816b60b267b6734a16f5614d8a41",  # DE 2-color 59×60 stub
    "8404669e8feb8303f78d34008ab4eab5",  # MN ultra-wide banner strip
    "d8c95963fee283a4ad2a87bb1b5620f7",  # CO banner strip
}

_CHROME_URL_RE = re.compile(
    r"(?:logo|icon|sprite|pixel|tracking|1x1|spacer|banner|button|"
    r"header|footer|nav|seal|badge|favicon|clear\.gif|blank\.gif|"
    r"/offices/|app_themes|webresource\.axd)",
    re.I,
)


def file_md5(path: Union[str, Path], *, chunk: int = 1 << 16) -> Optional[str]:
    """MD5 hex digest of a file, or None if unreadable."""
    try:
        p = Path(path)
        h = hashlib.md5()
        with p.open("rb") as f:
            while True:
                b = f.read(chunk)
                if not b:
                    break
                h.update(b)
        return h.hexdigest()
    except OSError:
        return None


def md5_bytes(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def url_looks_like_chrome(url: str) -> bool:
    """True when a remote image URL is almost certainly site chrome."""
    u = (url or "").strip()
    if not u:
        return True
    low = u.lower()
    if low.startswith("data:"):
        return True
    if "mugshot-placeholder" in low:
        return True
    if "crimewatch" in low and any(
        k in low for k in ("placeholder", "default", "stock", "arrest", "no-photo", "nophoto")
    ):
        return True
    if _CHROME_URL_RE.search(low):
        if any(
            k in low
            for k in (
                "displayimage", "callimage", "/pictures/", "sorimage",
                "imgid=", "imageid=", "offender", "mug",
            )
        ):
            if any(k in low for k in ("seal", "spacer", "logo", "1x1", "pixel", "favicon")):
                return True
            return False
        return True
    return False


def is_placeholder_photo_url(url: Optional[str]) -> bool:
    """True when a photo URL is a known no-photo / chrome stub."""
    return url_looks_like_chrome(str(url or ""))
