"""Schema v3 / deepface scan persistence smoke tests."""
from __future__ import annotations

import unittest

from tests.smoke._path import ROOT  # noqa: F401

from scraper.database import Database
from scraper.ethnic_names import EthnicNameDatabase


class SchemaV3Tests(unittest.TestCase):
    def test_photo_html_and_deepface_scan(self):
        db = Database.create_in_memory()
        try:
            r = db.import_records(
                [
                    {
                        "first_name": "Test",
                        "last_name": "Person",
                        "race": "White",
                        "source_url": "rb:1",
                        "source_system": "recentlybooked",
                        "photo_path": "data/photos/x.webp",
                        "html_path": "data/html/x.html",
                    }
                ]
            )
            self.assertEqual(r["imported"], 1)
            row = next(db.iter_arrests(source_system="recentlybooked", with_photos=True))
            self.assertEqual(row.get("html_path"), "data/html/x.html")
            db.upsert_deepface_scan(
                arrest_id=int(row["id"]),
                photo_path=row.get("photo_path"),
                top_label="black",
                top_confidence=0.91,
                is_hit=True,
                recorded_race="White",
            )
            hits = db.list_deepface_hits(source_system="recentlybooked")
            self.assertEqual(len(hits), 1)
        finally:
            db.close()

    def test_slavic_first_names_loaded(self):
        eth = EthnicNameDatabase()
        self.assertTrue(eth.slavic_first_names)
        _, conf_slavic, _ = eth.classify_by_name(
            "Gill", first_name="Andrei", middle_name=None
        )
        self.assertIsInstance(conf_slavic, float)


if __name__ == "__main__":
    unittest.main()
