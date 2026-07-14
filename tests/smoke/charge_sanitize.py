"""Smoke tests: non-charges rejected; spelled-out charges preferred."""
from __future__ import annotations

import unittest

from scraper.charge_expand import expand_charge, expand_charge_text
from scraper.charge_sanitize import (
    is_case_number,
    is_non_charge,
    is_state_name,
    pick_charge,
    sanitize_charge_text,
)
from scraper.charge_summary import summarize_charge


class ChargeSanitizeTests(unittest.TestCase):
    def test_alabama_not_a_charge(self):
        self.assertTrue(is_state_name("Alabama"))
        self.assertTrue(is_non_charge("Alabama"))
        self.assertEqual(sanitize_charge_text("Alabama"), "")
        self.assertEqual(expand_charge_text("Alabama"), "")
        self.assertEqual(summarize_charge("Alabama"), "—")

    def test_case_number_not_a_charge(self):
        samples = [
            "2026-CR-0000023",
            "2026 - CR- 0000023",
            "Charges Filed Case Number 26AJ-CR00037",
        ]
        for s in samples:
            self.assertTrue(is_case_number(s), s)
            self.assertTrue(is_non_charge(s), s)
            self.assertEqual(expand_charge_text(s), "", s)

    def test_warr_code_becomes_warrant(self):
        charge, case_no = pick_charge("WARR", "2026-CR-0000023")
        self.assertEqual(charge, "Warrant")
        self.assertEqual(case_no, "2026-CR-0000023")

    def test_real_offense_kept(self):
        charge, case_no = pick_charge("13A-6-21", "Assault 2nd")
        self.assertEqual(charge, "Assault 2nd")
        self.assertIsNone(case_no)

    def test_na_alabama_filtered(self):
        self.assertEqual(sanitize_charge_text("N/A; Alabama"), "")
        self.assertEqual(expand_charge_text("N/A; Alabama"), "")

    def test_recover_offense_from_raw(self):
        rec = {
            "charge_description": "Alabama",
            "raw_json": (
                '{"fields": {"Offense": "Bond revocation: Possess controlled substance"}}'
            ),
        }
        out = expand_charge(rec)
        self.assertIn("Possess", out)
        self.assertNotIn("Alabama", out)

    def test_mendoza_style_display(self):
        rec = {"charge_description": "2026-CR-0000023"}
        self.assertEqual(expand_charge(rec), "—")
        # After parser pick: stored as Warrant + case number
        rec2 = {
            "charge_description": "Warrant",
            "case_number": "2026-CR-0000023",
        }
        self.assertEqual(expand_charge(rec2), "Warrant")

    def test_no_data_to_display_rejected(self):
        junk = (
            "No Data To Display; # 1 # 2 Charge No Data To Display "
            "Count = 0 Offense Date Court Type Bond Bond Type "
            "Charging Agency Arresting Agency"
        )
        self.assertTrue(is_non_charge("No Data To Display"))
        self.assertEqual(sanitize_charge_text(junk), "")
        self.assertEqual(expand_charge(junk), "—")
        self.assertEqual(summarize_charge(junk), "—")

    def test_charge_description_chrome_stripped(self):
        raw = (
            "Charge Description ROBBERY 1ST Offense Date 1/2/2018 1:26 PM "
            "Attempt/Commit Commit"
        )
        self.assertEqual(sanitize_charge_text(raw), "ROBBERY 1ST")
        raw2 = (
            "BURGLARY 3RD; #1 #2 #3 Charge BURGLARY 3RD FTA Trafficking Meth "
            "Count=2 Offense Date 01-02-2022 Court Type Bond $15,000.00"
        )
        out = sanitize_charge_text(raw2)
        self.assertIn("BURGLARY 3RD", out)
        self.assertNotIn("Offense Date", out)
        self.assertNotIn("Count=", out)


if __name__ == "__main__":
    unittest.main()
