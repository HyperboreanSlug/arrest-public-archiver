"""Normalize / field-map smoke tests."""
from __future__ import annotations

import unittest

from tests.smoke._path import ROOT  # noqa: F401 — side-effect path bootstrap

from scraper.normalize import apply_field_map, stamp_source


class NormalizeTests(unittest.TestCase):
    def test_field_map_and_stamp(self):
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


if __name__ == "__main__":
    unittest.main()
