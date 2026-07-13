"""Smoke tests — misclassification is the primary product behavior."""

import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scraper.charge_classifications import classify_charge, classify_record
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

            garcia = next(m for m in hisp if (m.record.get("last_name") or "").lower() == "garcia")
            self.db.update_arrest(
                int(garcia.record["id"]),
                {"flags": '{"ethnicity_review": "correct"}'},
            )
            hisp2, _ = searcher.analyze_ethnicities(
                min_confidence=0.5,
                limit=0,
                ethnicity_filter="hispanic",
                return_base_count=True,
            )
            names_h2 = {(m.record.get("last_name") or "").lower() for m in hisp2}
            self.assertNotIn("garcia", names_h2)

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

    def test_first_name_confidence_parity(self):
        """SOR parity: ambiguous Indian surname + Anglo first name is low conf."""
        eth = EthnicNameDatabase()
        # Cristobal More should not be high-confidence Indian
        e1, c1, _ = eth.classify_by_name("More", first_name="Cristobal")
        self.assertFalse(
            e1.startswith("Indian") and c1 >= 0.5,
            f"More+Cristobal should not be high Indian conf (got {e1} {c1})",
        )
        # Indic first name can corroborate
        e2, c2, _ = eth.classify_by_name("Patel", first_name="Rahul")
        self.assertTrue(e2.startswith("Indian") or "Indian" in e2)
        self.assertGreaterEqual(c2, 0.5)

        searcher = ArrestSearcher(db_path=":memory:")
        orphan = searcher.db
        searcher.db = self.db
        self.db.import_records(
            [
                {
                    "first_name": "Cristobal",
                    "last_name": "More",
                    "race": "White",
                    "charge_description": "Theft",
                    "source_url": "fn:1",
                    "state": "FL",
                },
                {
                    "first_name": "Rahul",
                    "last_name": "Patel",
                    "race": "White",
                    "charge_description": "Theft",
                    "source_url": "fn:2",
                    "state": "FL",
                },
            ],
            skip_existing_urls=False,
        )
        try:
            results, base = searcher.analyze_ethnicities(
                min_confidence=0.5,
                ethnicity_filter="indian",
                return_base_count=True,
            )
            names = {
                (
                    (m.record.get("first_name") or ""),
                    (m.record.get("last_name") or "").lower(),
                )
                for m in results
            }
            # Patel+Rahul should appear; More+Cristobal should not at 0.5
            self.assertIn(("Rahul", "patel"), names)
            self.assertNotIn(("Cristobal", "more"), names)
        finally:
            searcher.db = orphan
            searcher.close()

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

    def test_charge_classifications_and_filter(self):
        self.assertEqual(classify_charge("RAPE FIRST DEGREE"), "sex_crimes")
        self.assertEqual(classify_charge("Breaking and Entering a dwelling"), "burglary_be")
        self.assertEqual(classify_charge("BURGLARY OF HABITATION"), "burglary_be")
        self.assertEqual(classify_charge("Possession of cocaine"), "drugs")
        self.assertEqual(classify_charge("DUI alcohol"), "dui_traffic")
        self.assertEqual(classify_charge("Aggravated assault with firearm"), "weapons")
        # weapons before violent when both match - "assault with firearm" has firearm first in weapons
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
            # Only sex_crimes Garcia, not burglary Garcia alone in sex filter
            self.assertEqual(len(sex), 1)

            be_rows = self.db.search_records(charge_category="burglary_be", limit=50)
            self.assertEqual(len(be_rows), 1)
            self.assertIn("Burglary", be_rows[0].get("charge_description") or "")
        finally:
            searcher.db = orphan
            searcher.close()


class RecentlyBookedParseTests(unittest.TestCase):
    def test_fixture_county_and_detail(self):
        from scraper.recentlybooked.parse import parse_county_cards, parse_detail

        fixtures = ROOT / "tests" / "fixtures"
        county = (fixtures / "recentlybooked_county.html").read_text(encoding="utf-8")
        cards = parse_county_cards(county)
        self.assertGreaterEqual(len(cards), 1)
        self.assertEqual(cards[0].get("source_system"), "recentlybooked")
        detail = (fixtures / "recentlybooked_detail.html").read_text(encoding="utf-8")
        rec = parse_detail(
            detail, "https://recentlybooked.com/xx/test-county/jane-doe~1_2"
        )
        self.assertEqual(rec.get("first_name"), "Jane")
        self.assertEqual(rec.get("last_name"), "Doe")
        self.assertTrue(rec.get("charge_description"))

    def test_homepage_mugshot_link_and_empty_booking_id(self):
        from scraper.recentlybooked.parse import parse_live_feed

        fixtures = ROOT / "tests" / "fixtures"
        html = (fixtures / "recentlybooked_live.html").read_text(encoding="utf-8")
        cards = parse_live_feed(html)
        self.assertEqual(len(cards), 2)
        self.assertEqual(cards[0]["county"], "broome")
        self.assertIn("location", cards[0])
        self.assertEqual(cards[1]["facility"], "1210")
        self.assertFalse(cards[1].get("booking_id"))

    def test_sitemap_locs_tolerate_misdecoded_bom(self):
        from scraper.recentlybooked.catalog import _sitemap_locs

        xml = (
            "ï»¿<?xml version=\"1.0\" encoding=\"utf-8\"?>"
            "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">"
            "<url><loc>https://recentlybooked.com/nj/essex</loc></url>"
            "</urlset>"
        )
        locs = _sitemap_locs(xml)
        self.assertEqual(locs, ["https://recentlybooked.com/nj/essex"])

    def test_name_suffix_not_used_as_last_name(self):
        from scraper.recentlybooked.parse import _name_parts

        parts = _name_parts("Reginald Trail Jr")
        self.assertEqual(parts.get("last_name"), "Trail")
        self.assertEqual(parts.get("name_suffix"), "Jr")

    def test_production_detail_strong_fields_and_charges(self):
        from scraper.recentlybooked.parse import parse_detail

        fixtures = ROOT / "tests" / "fixtures"
        html = (fixtures / "recentlybooked_detail_live.html").read_text(encoding="utf-8")
        rec = parse_detail(
            html, "https://recentlybooked.com/tx/brazos/zohaib-ayub~235_370356"
        )
        self.assertEqual(rec.get("race"), "Middle Eastern")
        self.assertEqual(rec.get("sex"), "M")
        self.assertIn("POSS CS", rec.get("charge_description") or "")
        self.assertIn("POSS MARIJ", rec.get("charge_description") or "")


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
        # Slavic given name dampens ambiguous Indian surname confidence vs Anglo
        _, conf_slavic, _ = eth.classify_by_name(
            "Gill", first_name="Andrei", middle_name=None
        )
        self.assertIsInstance(conf_slavic, float)


if __name__ == "__main__":
    unittest.main()
