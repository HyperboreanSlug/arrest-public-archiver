"""Only-*Asian* surname rules for misclassification detection.

English/American surnames that also appear on East/Southeast Asian lists
(Lee, Park, Long, Moon, …) must not mark race=White as an Asian
misclassification from name analysis alone.

A surname drives a high-confidence Asian label only when it is *only Asian*:
  * not on the shared White/Asian collision list, and
  * surname matches do not also hit a non-Asian family (Hispanic, European, …).
"""
from __future__ import annotations

from typing import Iterable, Optional, Tuple

# Common English/Irish/Scottish/German surnames (or short English words used as
# surnames) that collide with romanized Asian surnames in ethnic_names.json.
_SHARED_ASIAN_WHITE_SURNAMES = frozenset({
    # Classic Anglo / multi-use collisions
    "lee", "park", "long", "moon", "song", "law", "ham", "win", "san",
    "her", "eng", "lang", "ball", "hall", "wall", "hand", "land", "hard",
    "bond", "son", "man", "dan", "fan", "ran", "sean", "sam", "tim", "tom",
    "jim", "ray", "day", "may", "jay", "kay", "way", "gay", "roy", "ring",
    "wing", "king", "young",
    # Also on European lists; kept here so "only Asian" stays false if JSON drifts
    "bach", "jung", "david", "van", "neri",
})


def is_shared_asian_white_surname(surname: Optional[str]) -> bool:
    """True when the surname is common to White and Asian populations."""
    s = (surname or "").strip().lower()
    if not s:
        return False
    return s in _SHARED_ASIAN_WHITE_SURNAMES


def matches_are_only_asian(
    surname: Optional[str],
    matches: Iterable[Tuple[str, str]],
) -> bool:
    """True when name analysis may treat this surname as exclusively Asian.

    Requires at least one Asian match, no non-Asian family matches, and
    surname not on the shared White/Asian collision list.
    """
    if is_shared_asian_white_surname(surname):
        return False
    has_asian = False
    for ethnicity, _source in matches:
        eth = (ethnicity or "").strip()
        if eth.startswith("Asian"):
            has_asian = True
            continue
        # Any other family (Hispanic, European, Indian, …) → not only Asian
        return False
    return has_asian
