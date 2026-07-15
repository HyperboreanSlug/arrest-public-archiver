"""Mugshots.com HTML parse fixture tests."""
from __future__ import annotations

import unittest

from tests.smoke._path import ROOT


class MugshotsComParseTests(unittest.TestCase):
    def test_date_added_used_as_arrest_date(self):
        from scraper.mugshotscom.parse_detail import parse_detail

        fixtures = ROOT / "tests" / "fixtures"
        html = (fixtures / "mugshotscom_detail_date_added.html").read_text(
            encoding="utf-8"
        )
        url = (
            "https://mugshots.com/US-States/Arkansas/Carroll-County-AR/"
            "Divendra-Kumar-Patel.77941956.html"
        )
        rec = parse_detail(html, url)
        self.assertEqual(rec.get("arrest_date"), "2014-08-13")
        self.assertEqual(rec.get("booking_date"), "2014-08-13")
        self.assertEqual(rec.get("source_id"), "77941956")
        self.assertEqual(rec.get("state"), "AR")
        self.assertEqual(rec.get("county"), "carroll")
        self.assertEqual(rec.get("full_name"), "DIVENDRA KUMAR PATEL")
        self.assertEqual(rec.get("first_name"), "DIVENDRA")
        self.assertEqual(rec.get("last_name"), "PATEL")
        self.assertEqual(rec.get("date_of_birth"), "1975-07-01")
        self.assertEqual(rec.get("sex"), "M")
        self.assertEqual(rec.get("race"), "W")
        self.assertIn("SEXUAL ASSAULT", rec.get("charge_description") or "")

    def test_booking_date_not_overridden_by_date_added(self):
        from scraper.mugshotscom.parse_detail import parse_detail

        html = """
        <div class="item-date">Date added: 8/13/2014</div>
        <div class="field"><span class="name">Booking Date</span>
          <span class="value">1/15/2020 at 09:30</span></div>
        <div class="field"><span class="name">Name</span>
          <span class="value">Jane Doe</span></div>
        """
        rec = parse_detail(
            html,
            "https://mugshots.com/US-States/Arkansas/Carroll-County-AR/Jane-Doe.1.html",
        )
        self.assertEqual(rec.get("booking_date"), "2020-01-15")
        self.assertEqual(rec.get("arrest_time"), "09:30")
        self.assertIsNone(rec.get("arrest_date"))


if __name__ == "__main__":
    unittest.main()
