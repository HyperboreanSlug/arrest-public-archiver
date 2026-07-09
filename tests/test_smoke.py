"""Smoke tests — misclassification is the primary product behavior."""

import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scraper.database import Database
from scraper.normalize import apply_field_map, stamp_source
from scraper.searcher import ArrestSearcher
from scraper.ethnic_names import EthnicNameDatabase
from scraper.config import get_named_sources, get_bulk_sources


class NormalizeTests(unittest.TestCase):
    def test_field_map_and_fullname(self):
        row = {"Last Name": "Garcia", "First Name": "Ana", "Race": "White", "Charge": "Theft"}
        fmap = {
            "Last Name": "last_name",
            "First Name": "first_name",
            "Race": "race",
            "Charge": "charge_description",
        }
        rec = apply_field_map(row, fmap)
        rec = stamp_source(rec, source_id="test", state="MD", jurisdiction="Test")
        self.assertEqual(rec["last_name"], "Garcia")
        self.assertEqual(rec["full_name"], "Ana Garcia")
        self.assertEqual(rec["state"], "MD")
        self.assertTrue(rec.get("source_url"))


class DatabaseAndMisclassTests(unittest.TestCase):
    def setUp(self):
        self.db = Database.create_in_memory()

    def tearDown(self):
        self.db.close()

    def test_import_and_search(self):
        recs = [
            stamp_source(
                apply_field_map(
                    {
                        "First Name": "Juan",
                        "Last Name": "Garcia",
                        "Race": "White",
                        "Charge Description": "Assault",
                    },
                    {
                        "First Name": "first_name",
                        "Last Name": "last_name",
                        "Race": "race",
                        "Charge Description": "charge_description",
                    },
                ),
                source_id="demo",
                state="MD",
                jurisdiction="Demo",
            )
        ]
        recs[0]["source_url"] = "demo:1"
        r = self.db.import_records(recs)
        self.assertEqual(r["imported"], 1)
        rows = self.db.search_by_name("Garcia")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["race"], "White")

    def test_misclassify_primary_path(self):
        """Garcia recorded White → Hispanic misclass; Patel White → Indian."""
        batch = [
            {
                "first_name": "Juan",
                "last_name": "Garcia",
                "race": "White",
                "charge_description": "X",
                "state": "MD",
                "source_url": "t:1",
                "source_system": "t",
            },
            {
                "first_name": "Raj",
                "last_name": "Patel",
                "race": "White",
                "charge_description": "Y",
                "state": "MD",
                "source_url": "t:2",
                "source_system": "t",
            },
            {
                "first_name": "Bob",
                "last_name": "Smith",
                "race": "White",
                "charge_description": "Z",
                "state": "MD",
                "source_url": "t:3",
                "source_system": "t",
            },
            # No name — cannot misclassify
            {
                "race": "White",
                "charge_description": "Anon",
                "state": "CA",
                "source_url": "t:4",
                "source_system": "t",
            },
        ]
        self.db.import_records(batch)
        searcher = ArrestSearcher(db_path=":memory:")
        orphan = searcher.db
        searcher.db = self.db
        try:
            hisp, base_h = searcher.analyze_ethnicities(
                min_confidence=0.5,
                limit=0,
                ethnicity_filter="hispanic",
                return_base_count=True,
            )
            names_h = {(m.record.get("last_name") or "").lower() for m in hisp}
            self.assertIn("garcia", names_h)
            self.assertGreaterEqual(base_h, 1)

            indian, base_i = searcher.analyze_ethnicities(
                min_confidence=0.5,
                limit=0,
                ethnicity_filter="indian",
                return_base_count=True,
            )
            names_i = {(m.record.get("last_name") or "").lower() for m in indian}
            self.assertIn("patel", names_i)
            self.assertGreaterEqual(base_i, 1)
        finally:
            searcher.db = orphan
            searcher.close()

    def test_dedupe(self):
        # force insert duplicates (skip_existing would collapse them on import)
        self.db.import_records(
            [
                {"last_name": "A", "source_url": "u:1", "race": "W"},
                {"last_name": "A", "source_url": "u:1", "race": "B"},
                {"last_name": "B", "source_url": "u:2"},
            ],
            skip_existing_urls=False,
        )
        self.assertEqual(self.db.get_total_count(), 3)
        r = self.db.remove_duplicates("source_url", dry_run=False)
        self.assertEqual(r["deleted"], 1)
        self.assertEqual(self.db.get_total_count(), 2)

    def test_named_sources_exist(self):
        named = get_named_sources()
        self.assertTrue(any(s.id == "montgomery_md_arrests" for s in named))
        self.assertTrue(any(s.has_names for s in named))
        bulk = get_bulk_sources()
        self.assertGreaterEqual(len(bulk), 4)

    def test_ethnic_db_loads(self):
        eth = EthnicNameDatabase()
        self.assertTrue(eth.is_indian_surname("Singh") or eth.classify_by_name("Singh")[0].startswith("Indian"))
        self.assertEqual(eth.classify_by_name("Garcia")[0], "Hispanic")


if __name__ == "__main__":
    unittest.main()
