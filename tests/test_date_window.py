"""Last N days/weeks booking window helpers and search filter."""
from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from scraper.database import Database
from scraper.database.date_window import (
    cutoff_iso,
    resolve_cutoff,
    sql_since_date,
)


class DateWindowTests(unittest.TestCase):
    def test_cutoff_days_and_weeks(self):
        today = date(2026, 7, 19)
        self.assertEqual(cutoff_iso(days=7, today=today), "2026-07-12")
        self.assertEqual(cutoff_iso(weeks=2, today=today), "2026-07-05")
        self.assertIsNone(cutoff_iso(days=0, today=today))
        self.assertIsNone(cutoff_iso(weeks=-1, today=today))

    def test_resolve_cutoff_from_ui(self):
        today = date(2026, 7, 19)
        self.assertEqual(resolve_cutoff("7", "days", today=today), "2026-07-12")
        self.assertEqual(resolve_cutoff("1", "weeks", today=today), "2026-07-12")
        self.assertEqual(resolve_cutoff("2", "week", today=today), "2026-07-05")
        self.assertIsNone(resolve_cutoff("", "days", today=today))
        self.assertIsNone(resolve_cutoff("any", "days", today=today))
        self.assertIsNone(resolve_cutoff("x", "days", today=today))

    def test_sql_since_date_fragment(self):
        frag, params = sql_since_date("2026-07-01")
        self.assertIn("GLOB", frag)
        self.assertEqual(params, ["2026-07-01"])
        empty, empty_params = sql_since_date("")
        self.assertEqual(empty, "")
        self.assertEqual(empty_params, [])

    def test_search_records_since_date(self):
        tmp = Path(tempfile.mkdtemp()) / "dates.db"
        db = Database(str(tmp))
        try:
            db.import_records(
                [
                    {
                        "first_name": "New",
                        "last_name": "Book",
                        "race": "White",
                        "state": "FL",
                        "source_url": "date:new",
                        "arrest_date": "2026-07-15T10:00:00.000",
                    },
                    {
                        "first_name": "Old",
                        "last_name": "Book",
                        "race": "White",
                        "state": "FL",
                        "source_url": "date:old",
                        "arrest_date": "2026-06-01T10:00:00.000",
                    },
                    {
                        "first_name": "Slash",
                        "last_name": "Date",
                        "race": "White",
                        "state": "FL",
                        "source_url": "date:slash",
                        "arrest_date": "7/1/2026",
                    },
                    {
                        "first_name": "Booking",
                        "last_name": "Only",
                        "race": "Black",
                        "state": "FL",
                        "source_url": "date:booking",
                        "booking_date": "2026-07-18",
                    },
                ]
            )
            rows = db.search_records(since_date="2026-07-12", limit=0)
            urls = {r.get("source_url") for r in rows}
            self.assertIn("date:new", urls)
            self.assertIn("date:booking", urls)
            self.assertNotIn("date:old", urls)
            # Non-ISO slash dates are not treated as recent ISO matches
            self.assertNotIn("date:slash", urls)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
