"""Database import, search, and dedupe smoke tests."""
from __future__ import annotations

import unittest

from tests.smoke._path import ROOT  # noqa: F401

from scraper.config import get_bulk_sources, get_named_sources
from scraper.database import Database
from scraper.normalize import apply_field_map, stamp_source


class DatabaseCoreTests(unittest.TestCase):
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

    def test_dedupe(self):
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
        self.assertFalse(any(s.id == "bustednewspaper" for s in bulk))

    def test_dedupe_merges_multi_state_charges(self):
        self.db.import_records(
            [
                {
                    "first_name": "A",
                    "last_name": "Same",
                    "date_of_birth": "1990-01-01",
                    "state": "FL",
                    "charge_description": "Burglary",
                    "source_url": "m:1",
                },
                {
                    "first_name": "A",
                    "last_name": "Same",
                    "date_of_birth": "1990-01-01",
                    "state": "TX",
                    "charge_description": "Theft",
                    "source_url": "m:2",
                    "race": "White",
                },
            ],
            skip_existing_urls=False,
        )
        r = self.db.remove_duplicates("name_dob", dry_run=False, merge_fields=True)
        self.assertEqual(r["deleted"], 1)
        self.assertEqual(self.db.get_total_count(), 1)
        row = list(self.db.iter_arrests())[0]
        states = (row.get("state") or "")
        self.assertIn("FL", states)
        self.assertIn("TX", states)
        charges = (row.get("charge_description") or "")
        self.assertIn("Burglary", charges)
        self.assertIn("Theft", charges)
        self.assertEqual(row.get("race"), "White")


if __name__ == "__main__":
    unittest.main()
