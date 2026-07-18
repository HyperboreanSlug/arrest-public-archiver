"""Map NC DAC table rows to MAPA canonical arrest records."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

SOURCE_SYSTEM = "nc_dac"
OPI_URL = (
    "https://webapps.doc.state.nc.us/opi/offendersearch.do?method=view"
)


def _title(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return " ".join(p.capitalize() for p in value.split())


def _normalize_sex(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    u = value.strip().upper()
    if u in ("M", "MALE"):
        return "Male"
    if u in ("F", "FEMALE"):
        return "Female"
    return value.strip().title()


def _normalize_race(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    u = value.strip().upper()
    mapping = {
        "WHITE": "White",
        "BLACK": "Black",
        "BLACK/AFRICAN AMERICAN": "Black",
        "ASIAN": "Asian",
        "ASIAN/ASIAN AMERICAN": "Asian",
        "AMERICAN INDIAN": "American Indian",
        "AMERICAN INDIAN/ALASKAN NATIVE": "American Indian",
        "HAWAIIAN/PACIFIC ISLANDER": "Pacific Islander",
        "OTHER": "Other",
        "UNKNOWN": None,
    }
    return mapping.get(u, value.strip().title())


def _normalize_ethnicity(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    u = value.strip().upper()
    if u in ("UNKNOWN",):
        return None
    if "HISPANIC" in u or "LATINO" in u:
        if u.startswith("NOT"):
            return "Not Hispanic/Latino"
        return "Hispanic/Latino"
    return value.strip().title()


def _height_from_inches(raw: Optional[str]) -> Optional[str]:
    if not raw or not raw.isdigit():
        return None
    inches = int(raw)
    if inches <= 0 or inches > 96:
        return None
    return f"{inches // 12}'{inches % 12}\""


def map_inmate_row(
    row: Dict[str, Optional[str]],
    *,
    profile: Optional[Dict[str, Optional[str]]] = None,
) -> Dict[str, Any]:
    """Map INMT4AA1 (+ optional OFNT3AA1 profile) to a canonical record."""
    doc = (row.get("CIDORNUM") or "").strip()
    last = _title(row.get("CICLSTNM"))
    first = _title(row.get("CICFSTNM"))
    middle = _title(row.get("CICMIDIN"))
    suffix = _title(row.get("CICSUFIX"))
    parts = [p for p in (first, middle, last) if p]
    full = " ".join(parts) if parts else None
    if suffix and full:
        full = f"{full} {suffix}"

    offense = row.get("CIPRIOFF")
    charge_level = row.get("CIFELONY")
    if charge_level:
        cl = charge_level.upper()
        if cl.startswith("FEL"):
            charge_level = "Felony"
        elif cl.startswith("MIS"):
            charge_level = "Misdemeanor"

    facility = row.get("CICURLOC")
    agency = facility or "NC Department of Adult Correction"

    rec: Dict[str, Any] = {
        "first_name": first,
        "middle_name": middle,
        "last_name": last,
        "full_name": full,
        "sex": _normalize_sex(row.get("CICLSEX")),
        "gender": _normalize_sex(row.get("CICLSEX")),
        "race": _normalize_race(row.get("CICLRACE")),
        "ethnicity": _normalize_ethnicity(row.get("CIETHNIC")),
        "date_of_birth": row.get("CICLBRTH"),
        "booking_date": row.get("CIRADMDT"),
        "arrest_date": row.get("CIRADMDT"),
        "release_date": row.get("GIRMAX"),
        "agency": agency,
        "jurisdiction": "North Carolina DAC",
        "state": "NC",
        "county": None,
        "charge_description": offense,
        "charge_level": charge_level,
        "booking_id": doc or None,
        "source_id": f"nc_dac:{doc}" if doc else None,
        "source_url": (
            f"https://webapps.doc.state.nc.us/opi/offendersearch.do"
            f"?method=view&offenderID={doc}"
            if doc
            else OPI_URL
        ),
        "source_system": SOURCE_SYSTEM,
    }

    # Physicals from offender profile join when present
    if profile:
        rec["height"] = _height_from_inches(profile.get("CMCLHITE"))
        w = profile.get("CMWEIGHT")
        if w and str(w).isdigit() and int(w) > 0:
            rec["weight"] = str(int(w))
        hair = profile.get("CMHAIR")
        eyes = profile.get("CMCLEYEC")
        if hair and hair.upper() != "UNKNOWN":
            rec["hair"] = hair.title()
        if eyes and eyes.upper() != "UNKNOWN":
            rec["eyes"] = eyes.title()
        if not rec.get("ethnicity"):
            rec["ethnicity"] = _normalize_ethnicity(profile.get("CMETHNIC"))

    # Keep useful raw context (compact)
    raw = {
        "doc_number": doc,
        "record_status": row.get("INMRCDSTA"),
        "admin_status": row.get("CIINSTAT"),
        "custody": row.get("CICCLASS"),
        "facility": facility,
        "primary_offense": offense,
        "most_serious_qualifier": row.get("CIPRIQLF"),
        "admission_date": row.get("CIRADMDT"),
        "conviction_date": row.get("CICONVDT"),
    }
    rec["raw_json"] = json.dumps(raw, ensure_ascii=False, separators=(",", ":"))
    return rec


def map_supervision_row(row: Dict[str, Optional[str]]) -> Dict[str, Any]:
    """Map APPT7AA1 (probation/parole client profile) to a canonical record."""
    doc = (row.get("CDDORNUM") or "").strip()
    last = _title(row.get("CDSLSTNM"))
    first = _title(row.get("CDSFSTNM"))
    middle = _title(row.get("CDSMIDNM"))
    suffix = _title(row.get("CDSSUFFX"))
    parts = [p for p in (first, middle, last) if p]
    full = " ".join(parts) if parts else None
    if suffix and full:
        full = f"{full} {suffix}"

    offense = row.get("PRIOFFNSE")
    charge_level = row.get("CDFELONY")
    if charge_level:
        cl = charge_level.upper()
        if cl.startswith("FEL"):
            charge_level = "Felony"
        elif cl.startswith("MIS"):
            charge_level = "Misdemeanor"

    office = row.get("CDPPSLOC")
    rec: Dict[str, Any] = {
        "first_name": first,
        "middle_name": middle,
        "last_name": last,
        "full_name": full,
        "sex": _normalize_sex(row.get("CDCLSEX")),
        "gender": _normalize_sex(row.get("CDCLSEX")),
        "race": _normalize_race(row.get("CDCLRACE")),
        "date_of_birth": row.get("CDCLBRTH"),
        "agency": office or "NC DAC Community Supervision",
        "jurisdiction": "North Carolina DAC",
        "state": "NC",
        "charge_description": offense,
        "charge_level": charge_level,
        "booking_id": doc or None,
        "source_id": f"nc_dac_pp:{doc}" if doc else None,
        "source_url": (
            f"https://webapps.doc.state.nc.us/opi/offendersearch.do"
            f"?method=view&offenderID={doc}"
            if doc
            else OPI_URL
        ),
        "source_system": SOURCE_SYSTEM,
    }
    raw = {
        "doc_number": doc,
        "kind": "probation_parole",
        "record_status": row.get("PPRCDSTA"),
        "admin_status": row.get("GDSTATUS"),
        "office": office,
        "primary_offense": offense,
        "supervision_length": row.get("CDSUPLTH"),
    }
    rec["raw_json"] = json.dumps(raw, ensure_ascii=False, separators=(",", ":"))
    return rec
