"""Ordered charge-summary rules: first match wins per segment."""
from __future__ import annotations

import re
from typing import List, Tuple

from scraper.charge_summary_rules_a import _SUMMARY_RULES_A
from scraper.charge_summary_rules_b import _SUMMARY_RULES_B
from scraper.charge_summary_rules_c import _SUMMARY_RULES_C

_SUMMARY_RULES: List[Tuple[str, List[str]]] = (
    list(_SUMMARY_RULES_A) + list(_SUMMARY_RULES_B) + list(_SUMMARY_RULES_C)
)

_COMPILED: List[Tuple[str, List[re.Pattern]]] = [
    (label, [re.compile(p, re.IGNORECASE) for p in pats])
    for label, pats in _SUMMARY_RULES
]
