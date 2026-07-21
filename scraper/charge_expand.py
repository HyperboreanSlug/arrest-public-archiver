"""Expand jail booking abbreviations into full plain-language charges."""
from __future__ import annotations

import re
from typing import Any, List

from scraper.charge_expand_phrases import EXPAND_PHRASES

# Whole-token map (applied after phrases). Keys are uppercase.
_TOKENS = {
    "ASSLT": "Assault",
    "AGG": "Aggravated",
    "AGGRAV": "Aggravated",
    "CBI": "Causes Bodily Injury",
    "SBI": "Serious Bodily Injury",
    "FV": "Family Violence",
    "UNL": "Unlawful",
    "POSS": "Possession",
    "CS": "Controlled Substance",
    "MARIJ": "Marijuana",
    "MARIJUANA": "Marijuana",
    "FTA": "Failure to Appear",
    "FRM": "From",
    "DWI": "Driving While Intoxicated",
    "DUI": "Driving Under the Influence",
    "OWI": "Operating While Intoxicated",
    "OVI": "Operating a Vehicle Impaired",
    "PG": "Penalty Group",
    "DOM": "Domestic",
    "VIOL": "Violation",
    "PROTECT": "Protective",
    "PROTECTIVE": "Protective",
    "RESTRAINT": "Restraint",
    "WEAPON": "Weapon",
    "WEAPONS": "Weapons",
    "FIREARM": "Firearm",
    "FELON": "Felon",
    "DEADLY": "Deadly",
    "BODILY": "Bodily",
    "INJ": "Injury",
    "INJRY": "Injury",
    "INJURY": "Injury",
    "PHY": "Physical",
    "PHYSICAL": "Physical",
    "FAMILY": "Family",
    "MEMBER": "Member",
    "ASSAULT": "Assault",
    "BATTERY": "Battery",
    "SEX": "Sexual",
    "SEXUAL": "Sexual",
    "ATT": "Attempted",
    "ATTEMPTED": "Attempted",
    "EVADING": "Evading",
    "ARREST": "Arrest",
    "DETENTION": "Detention",
    "THEFT": "Theft",
    "CRIMINAL": "Criminal",
    "MISCHIEF": "Mischief",
    "RESIST": "Resisting",
    "RESISTING": "Resisting",
    "OBSTRUCT": "Obstructing",
    "LEO": "Law Enforcement Officer",
    "SMPL": "Simple",
    "SIMPLE": "Simple",
    "INTOXICATED": "Intoxicated",
    "INTOX": "Intoxicated",
    "OPEN": "Open",
    "ALCH": "Alcohol",
    "CONTAINER": "Container",
    "MAN": "Manufacture",
    "DEL": "Delivery",
    "PROH": "Prohibited",
    "PROHIBITED": "Prohibited",
    "BOND": "Bond",
    "ORDER": "Order",
    "COURT": "Court",
    "WARR": "Warrant",
    "WARRANT": "Warrant",
    "BENCH": "Bench",
    "FUGITIVE": "Fugitive",
    "JUSTICE": "Justice",
    "PAROLE": "Parole",
    "PROBATION": "Probation",
    "PROB": "Probation",
    "PAR": "Parole",
    "HOLD": "Hold",
    "ICE": "Immigration and Customs Enforcement",
    "IMMIGRATION": "Immigration",
    "VEH": "Vehicle",
    "VEHICLE": "Vehicle",
    "MOTOR": "Motor",
    "LARC": "Larceny",
    "LARCENY": "Larceny",
    "UNAUTH": "Unauthorized",
    "UNAUTHORIZED": "Unauthorized",
    "CONT": "Controlled",
    "SUB": "Substance",
    "SUBST": "Substance",
    "OFF": "Offense",
    "PUBLIC": "Public",
    "OFFICER": "Officer",
    "ENTER": "Enter",
    "BREAK": "Breaking",
    "DISTRIB": "Distribution",
    "FACIL": "Facilitate",
    "DRIV": "Driving",
    "OBT": "Obtain",
    "PROP": "Property",
    "PR": "Pretenses",
    "CHTS": "Cheat",
    "SER": "Services",
    "ATTEM": "Attempt",
    "PARA": "Paraphernalia",
    "DISCHG": "Discharging",
    "UNLAWFL": "Unlawful",
    "SOLICIT": "Solicitation",
    "REGIS": "Registration",
    "REVOKE": "Revoked",
    "REVOKED": "Revoked",
    "SUSP": "Suspended",
    "SUSPEND": "Suspended",
    "SUSPENDED": "Suspended",
    "LIC": "License",
    "LICENSE": "License",
    "PERM": "Permit",
    "RVK": "Revoked",
    "MISC": "Miscellaneous",
    "MISD": "Misdemeanor",
    "FEL": "Felony",
    "HABIT": "Habitation",
    "BLDG": "Building",
    "WPN": "Weapon",
    "KNIF": "Knife",
    "AMMO": "Ammunition",
    "POCS": "Possession of Controlled Substance",
    "PCS": "Possession of Controlled Substance",
    "ASLT": "Assault",
    "OCC": "Occupied",
    "BURG": "Burglary",
    "COMM": "Commit",
    "ELUD": "Elude",
    "ATTEMPT": "Attempt",
}

# Class letter at segment start: A/B/C misdemeanor, F felony.
_CLASS_PREFIX = re.compile(r"^\s*([ABC])\s+(?=[A-Za-z])", re.IGNORECASE)
_FELONY_PREFIX = re.compile(r"^\s*F\s+(?=[A-Za-z])", re.IGNORECASE)
_SPLIT = re.compile(r"\s*[;|]\s*")
# Do not keep '/' inside tokens so BREAK/ENTER splits for mapping.
_WORD = re.compile(r"[A-Za-z][A-Za-z'.-]*|\d+(?:st|nd|rd|th)?|\d+(?:\.\d+)?|[^\s]")
_ORD_GLUED = re.compile(r"(?i)^(\d+)(st|nd|rd|th)$")


def _expand_segment(segment: str) -> str:
    s = " ".join((segment or "").replace("\u00a0", " ").split())
    if not s:
        return ""
    class_note = ""
    m = _CLASS_PREFIX.match(s)
    if m:
        class_note = f"Class {m.group(1).upper()} Misdemeanor "
        s = s[m.end() :]
    else:
        m = _FELONY_PREFIX.match(s)
        if m:
            class_note = "Felony "
            s = s[m.end() :]
    for pat, repl in EXPAND_PHRASES:
        s = re.sub(pat, repl, s, flags=re.IGNORECASE)
    # Protect compact statute fragments like 1/1-B before slash-splitting.
    protected: list[str] = []

    def _protect(m: re.Match) -> str:
        protected.append(m.group(0))
        return f" __P{len(protected) - 1}__ "

    s = re.sub(r"\b\d+\s*/\s*\d+[A-Za-z0-9.-]*\b", _protect, s)
    # Remaining jail slashes → spaces (DATE/FAMILY leftovers, etc.)
    s = re.sub(r"\s*/\s*", " ", s)
    for i, val in enumerate(protected):
        s = s.replace(f"__P{i}__", val)
    s = re.sub(r"\s+", " ", s).strip()
    # Phrase output is already plain English — do not re-Title every word.
    if not _needs_token_expand(s):
        out = s
    else:
        parts: List[str] = []
        for tok in _WORD.findall(s):
            key = tok.upper().rstrip(".")
            om = _ORD_GLUED.match(tok)
            if om:
                parts.append(f"{om.group(1)}{om.group(2).lower()}")
                continue
            if key in _TOKENS:
                parts.append(_TOKENS[key])
            elif tok.isalpha() and tok.isupper() and len(tok) <= 4 and key not in _TOKENS:
                parts.append(tok.title() if len(tok) > 1 else tok.upper())
            elif tok.isalpha() and tok.isupper():
                parts.append(tok.title())
            else:
                parts.append(tok if not tok.isalpha() else tok.title())
        out = re.sub(r"\s+", " ", " ".join(parts)).strip(" ,.;:-")
    out = re.sub(r"\s+([,.;:])", r"\1", out)
    out = re.sub(r"\(\s+", "(", out)
    out = re.sub(r"\s+\)", ")", out)
    out = re.sub(r"\b(With)\s+\1\b", r"\1", out, flags=re.IGNORECASE)
    # "1th Degree" from phrase backref fix when ordinal was 1ST
    out = re.sub(
        r"\b(\d+)th Degree\b",
        lambda m: _ordinal_label(int(m.group(1))),
        out,
        flags=re.IGNORECASE,
    )
    return (class_note + out).strip()


def _needs_token_expand(text: str) -> bool:
    """True when segment still has jail ALLCAPS codes needing token maps."""
    for tok in _WORD.findall(text or ""):
        if tok.isalpha() and tok.isupper() and len(tok) >= 2:
            return True
    return False


def _ordinal_label(n: int) -> str:
    mod100 = n % 100
    if 10 < mod100 < 14:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf} Degree"


def expand_charge_text(text: str) -> str:
    """Expand abbreviations in raw charge text; keep multi-charge separators."""
    from scraper.charge_sanitize import is_non_charge, sanitize_charge_text

    raw = sanitize_charge_text(" ".join((text or "").replace("\u00a0", " ").split()))
    if not raw or is_non_charge(raw):
        return ""
    segs = [p for p in _SPLIT.split(raw) if p and p.strip()] or [raw]
    expanded = [
        e for e in (_expand_segment(p) for p in segs) if e and not is_non_charge(e)
    ]
    return "; ".join(expanded)


def expand_charge(record_or_text: Any) -> str:
    """Full plain-language charge for details and export cards."""
    from scraper.charge_recover import recover_charge_from_record

    if record_or_text is None:
        return "—"
    if isinstance(record_or_text, dict):
        parts = [
            record_or_text.get(k)
            for k in (
                "charge_description",
                "charge_group",
                "offense",
                "offense_description",
                "statute",
            )
        ]
        blob = " | ".join(str(p) for p in parts if p and str(p).strip())
        out = expand_charge_text(blob)
        if out:
            return out
        recovered = recover_charge_from_record(record_or_text)
        return expand_charge_text(recovered) if recovered else "—"
    return expand_charge_text(str(record_or_text)) or "—"
