"""Charge classification and charge-filtered misclass smoke tests."""
from __future__ import annotations

import unittest

from tests.smoke._path import ROOT  # noqa: F401

from scraper.charge_classifications import classify_charge, classify_record
from scraper.database import Database
from scraper.searcher import ArrestSearcher


class ChargeFilterTests(unittest.TestCase):
    def setUp(self):
        self.db = Database.create_in_memory()

    def tearDown(self):
        self.db.close()

    def test_charge_classifications_and_filter(self):
        self.assertEqual(classify_charge("RAPE FIRST DEGREE"), "sex_crimes")
        self.assertEqual(classify_charge("Breaking and Entering a dwelling"), "burglary_be")
        self.assertEqual(classify_charge("BURGLARY OF HABITATION"), "burglary_be")
        self.assertEqual(classify_charge("Possession of cocaine"), "drugs")
        self.assertEqual(classify_charge("DUI alcohol"), "dui_traffic")
        self.assertEqual(classify_charge("Aggravated assault with firearm"), "weapons")
        self.assertEqual(classify_charge("Simple assault"), "violent")
        self.assertEqual(classify_charge(""), "unknown")

        batch = [
            {
                "first_name": "A", "last_name": "Garcia", "race": "White",
                "charge_description": "Sexual assault of a child",
                "state": "MD", "source_url": "c:1",
            },
            {
                "first_name": "B", "last_name": "Garcia", "race": "White",
                "charge_description": "Burglary second degree",
                "state": "MD", "source_url": "c:2",
            },
            {
                "first_name": "C", "last_name": "Smith", "race": "White",
                "charge_description": "Shoplifting",
                "state": "MD", "source_url": "c:3",
            },
        ]
        for r in batch:
            classify_record(r)
        self.assertEqual(batch[0]["charge_category"], "sex_crimes")
        self.assertEqual(batch[1]["charge_category"], "burglary_be")
        self.db.import_records(batch, skip_existing_urls=False)

        searcher = ArrestSearcher(db_path=":memory:")
        orphan = searcher.db
        searcher.db = self.db
        try:
            sex, base = searcher.analyze_ethnicities(
                min_confidence=0.5,
                ethnicity_filter="hispanic",
                charge_category="sex_crimes",
                return_base_count=True,
            )
            self.assertGreaterEqual(base, 1)
            names = {(m.record.get("last_name") or "").lower() for m in sex}
            self.assertIn("garcia", names)
            self.assertEqual(len(sex), 1)

            be_rows = self.db.search_records(charge_category="burglary_be", limit=50)
            self.assertEqual(len(be_rows), 1)
            self.assertIn("Burglary", be_rows[0].get("charge_description") or "")
        finally:
            searcher.db = orphan
            searcher.close()


if __name__ == "__main__":
    unittest.main()
