"""
Configuration for public arrest / booking open-data sources.

Primary product goal: archive published arrest records and flag ethnic
surname vs recorded-race mismatches (misclassification analysis).

scrape_method:
  - socrata:   Socrata SODA API / CSV export (domain + dataset_id)
  - direct:    published bulk CSV/JSON URL(s)
  - interactive: search-only or no automated bulk path
  - stats_only: aggregates only (not person-level browse)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

USER_AGENT = (
    "ArrestPublicArchiver/0.1 (+https://github.com/HyperboreanSlug/arrest-public-archiver; "
    "public open-data research; polite rate limits)"
)
DEFAULT_DELAY = 1.0
MAX_RETRIES = 3
REQUEST_TIMEOUT = 60


@dataclass
class ArrestSource:
    """One open-data or bulk arrest/booking feed."""

    id: str
    name: str
    state: str
    jurisdiction: str  # city / county / state agency label
    scrape_method: str = "interactive"
    # Socrata
    socrata_domain: Optional[str] = None
    socrata_dataset_id: Optional[str] = None
    # Direct bulk
    direct_downloads: List[str] = field(default_factory=list)
    portal_url: Optional[str] = None
    # Map source column names → canonical arrest fields
    field_map: Dict[str, str] = field(default_factory=dict)
    # Cap rows for polite first-run tests (0 = unlimited)
    default_row_limit: int = 0
    status: str = "verified_bulk"  # verified_bulk | interactive | stats_only | broken
    notes: str = ""
    # True when published rows typically include a personal name
    has_names: bool = True


# Tier A open-data sources (MVP). Field maps are best-effort and may need tweaks
# after live schema checks.
SOURCES: List[ArrestSource] = [
    ArrestSource(
        id="la_arrests",
        name="Los Angeles PD Arrests",
        state="CA",
        jurisdiction="Los Angeles",
        scrape_method="socrata",
        socrata_domain="data.lacity.org",
        socrata_dataset_id="amvf-fr72",
        portal_url="https://data.lacity.org/Public-Safety/Arrest-Data-from-2020-to-4-30-2025/amvf-fr72",
        field_map={
            "Report ID": "source_id",
            "ReportID": "source_id",
            "Arrest Date": "arrest_date",
            "Time": "arrest_time",
            "Area Name": "agency",
            "Age": "age",
            "Sex Code": "sex",
            "Descent Code": "race",
            "Charge Group Description": "charge_description",
            "Charge Description": "charge_description",
            "Charge": "statute",
            "Address": "address",
            "LAT": "latitude",
            "LON": "longitude",
        },
        default_row_limit=5000,
        notes=(
            "LAPD open data. Descent codes (A/B/H/O/W/…) rather than full names "
            "in many exports — verify columns live. Primary use: race vs surname "
            "when names appear, or charge/race stats."
        ),
        has_names=False,
        status="verified_bulk",
    ),
    ArrestSource(
        id="chicago_arrests",
        name="Chicago PD Arrests",
        state="IL",
        jurisdiction="Chicago",
        scrape_method="socrata",
        socrata_domain="data.cityofchicago.org",
        socrata_dataset_id="dpt3-jri9",
        portal_url="https://data.cityofchicago.org/Public-Safety/Arrests/dpt3-jri9",
        field_map={
            "CB_NO": "source_id",
            "CASE NUMBER": "case_number",
            "ARREST DATE": "arrest_date",
            "RACE": "race",
            "CHARGE 1 STATUTE": "statute",
            "CHARGE 1 DESCRIPTION": "charge_description",
            "CHARGE 1 TYPE": "charge_level",
            "CHARGE 1 CLASS": "charge_class",
        },
        default_row_limit=5000,
        notes="Public CPD Arrests dataset; detailed name fields may be limited on public export.",
        has_names=False,
        status="verified_bulk",
    ),
    ArrestSource(
        id="seattle_arrests",
        name="Seattle PD Arrest Data",
        state="WA",
        jurisdiction="Seattle",
        scrape_method="socrata",
        socrata_domain="data.seattle.gov",
        socrata_dataset_id="9bjs-7a7w",
        portal_url="https://data.seattle.gov/Public-Safety/SPD-Arrest-Data/9bjs-7a7w",
        field_map={
            "Offense_ID": "source_id",
            "Arrest_Date": "arrest_date",
            "Crime_Against_Category": "charge_level",
            "Offense": "charge_description",
            "Offense_Category": "charge_group",
            "Race": "race",
            "Sex": "sex",
            "Age": "age",
            "Precinct": "agency",
        },
        default_row_limit=5000,
        notes="SPD arrest open data; field names vary by export version.",
        has_names=False,
        status="verified_bulk",
    ),
    ArrestSource(
        id="montgomery_md_arrests",
        name="Montgomery County MD Daily Arrests",
        state="MD",
        jurisdiction="Montgomery County",
        scrape_method="socrata",
        socrata_domain="data.montgomerycountymd.gov",
        socrata_dataset_id="xhwt-7h2h",
        portal_url="https://data.montgomerycountymd.gov/Public-Safety/Daily-Arrests/xhwt-7h2h",
        field_map={
            "Last Name": "last_name",
            "First Name": "first_name",
            "Middle Name": "middle_name",
            "Race": "race",
            "Sex": "sex",
            "Age": "age",
            "Arrest Date": "arrest_date",
            "Arrest Number": "source_id",
            "Charge": "charge_description",
            "Charge Description": "charge_description",
            "City": "city",
            "State": "state",
        },
        default_row_limit=0,
        notes="County daily arrests — typically includes names (strong for misclassification).",
        has_names=True,
        status="verified_bulk",
    ),
    ArrestSource(
        id="king_wa_bookings",
        name="King County WA Adult Jail Bookings",
        state="WA",
        jurisdiction="King County",
        scrape_method="socrata",
        socrata_domain="data.kingcounty.gov",
        socrata_dataset_id="j56h-zgnm",
        portal_url="https://data.kingcounty.gov/",
        field_map={
            "BookingId": "booking_id",
            "Booking Number": "booking_id",
            "Last Name": "last_name",
            "First Name": "first_name",
            "Middle Name": "middle_name",
            "Race": "race",
            "Sex": "sex",
            "Booking Date Time": "booking_date",
            "Release Date Time": "release_date",
            "Charge Description": "charge_description",
            "Facility": "agency",
        },
        default_row_limit=5000,
        notes="Jail bookings open data — names usually present (primary misclass feed).",
        has_names=True,
        status="verified_bulk",
    ),
    ArrestSource(
        id="sf_arrests",
        name="San Francisco Police Incident / Arrest open data",
        state="CA",
        jurisdiction="San Francisco",
        scrape_method="socrata",
        socrata_domain="data.sfgov.org",
        socrata_dataset_id="wg3w-h783",
        portal_url="https://data.sfgov.org/",
        field_map={
            "Incident Number": "source_id",
            "Incident Date": "arrest_date",
            "Incident Description": "charge_description",
            "Incident Category": "charge_group",
            "Police District": "agency",
            "Analysis Neighborhood": "city",
        },
        default_row_limit=5000,
        notes="Often incident-centric; verify whether arrestee names/race are published.",
        has_names=False,
        status="verified_bulk",
    ),
]


def get_source(source_id: str) -> Optional[ArrestSource]:
    sid = (source_id or "").strip().lower()
    for s in SOURCES:
        if s.id.lower() == sid:
            return s
    return None


def get_bulk_sources() -> List[ArrestSource]:
    return [s for s in SOURCES if s.scrape_method in ("socrata", "direct") and s.status == "verified_bulk"]


def get_named_sources() -> List[ArrestSource]:
    """Sources most useful for surname/race misclassification (publish names)."""
    return [s for s in get_bulk_sources() if s.has_names]
