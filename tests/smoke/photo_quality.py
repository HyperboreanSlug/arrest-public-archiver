"""Photo quality / placeholder detection smoke tests."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.smoke._path import ROOT  # noqa: F401


class PhotoQualityTests(unittest.TestCase):
    def test_crimewatch_stock_placeholder_filtered(self):
        """CrimeWatch 'ARREST' handcuffs tiles are not real mugshots."""
        from PIL import Image, ImageDraw

        from scraper.mugshot_ethnicity.photo_quality import (
            KNOWN_PLACEHOLDER_MD5,
            bytes_non_mugshot_reason,
            clear_placeholder_cache,
            is_placeholder_photo,
            record_has_real_photo,
        )

        clear_placeholder_cache()
        # Synthetic signature: dark frame + blue banner + red badge
        im = Image.new("RGB", (250, 250), (18, 18, 18))
        draw = ImageDraw.Draw(im)
        draw.rectangle((0, 195, 249, 249), fill=(20, 50, 160))
        draw.rectangle((8, 205, 55, 240), fill=(200, 30, 30))
        draw.ellipse((70, 60, 180, 170), outline=(180, 180, 190), width=8)

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "crimewatch_stub.webp"
            im.save(path, format="WEBP", quality=80)
            self.assertTrue(is_placeholder_photo(path))
            data = path.read_bytes()
            reason = bytes_non_mugshot_reason(
                data,
                url="https://recentlybooked.com/images/680/999999.webp",
                ext=".webp",
            )
            self.assertIsNotNone(reason)
            self.assertIn("CrimeWatch", reason or "")
            rec = {
                "photo_path": str(path),
                "photo_url": "https://recentlybooked.com/images/680/999999.webp",
            }
            self.assertFalse(record_has_real_photo(rec))

        self.assertIn("8558ffafb796af4dacd58e85145b3138", KNOWN_PLACEHOLDER_MD5)

    def test_real_face_not_flagged_as_crimewatch(self):
        from PIL import Image

        from scraper.mugshot_ethnicity.photo_quality import (
            clear_placeholder_cache,
            is_placeholder_photo,
        )

        clear_placeholder_cache()
        # Mid-tone face-like frame without blue banner / red badge
        im = Image.new("RGB", (250, 250), (160, 130, 110))
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "face.webp"
            im.save(path, format="WEBP", quality=80)
            self.assertFalse(is_placeholder_photo(path))

    def test_gray_photo_not_available_placeholder(self):
        """mugshots.com gray 'photo not available' tiles are not mugshots."""
        from PIL import Image

        from scraper.mugshot_ethnicity.photo_quality import (
            KNOWN_PLACEHOLDER_MD5,
            bytes_non_mugshot_reason,
            clear_placeholder_cache,
            is_placeholder_photo,
            record_has_real_photo,
        )

        clear_placeholder_cache()
        self.assertIn("acca619e6684d7ff5e7ad8d8a79ca6f3", KNOWN_PLACEHOLDER_MD5)
        # Near-uniform mid-gray field (site stub look)
        im = Image.new("RGB", (400, 500), (218, 218, 218))
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "gray_stub.jpg"
            im.save(path, format="JPEG", quality=85)
            self.assertTrue(is_placeholder_photo(path))
            reason = bytes_non_mugshot_reason(path.read_bytes(), ext=".jpg")
            self.assertIsNotNone(reason)
            self.assertIn("gray", (reason or "").lower())
            rec = {"photo_path": str(path), "photo_url": "https://example/x.jpg"}
            self.assertFalse(record_has_real_photo(rec))


if __name__ == "__main__":
    unittest.main()
