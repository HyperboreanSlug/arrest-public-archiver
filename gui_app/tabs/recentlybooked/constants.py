"""RecentlyBooked tab constants and mugshot source option loading."""
from __future__ import annotations

_RB_COLS = ["name", "race", "state", "county", "charge", "hint"]
_RB_WIDTHS = [180, 80, 50, 100, 200, 140]
# Mugshot HTML sources shown under the RecentlyBooked tab (not open-data Scrape).
# Populated from scraper.mugshot_sources (RB, Mugshots.com, BN, …).
try:
    from scraper.mugshot_sources import source_labels as _ms_source_labels
    from scraper.mugshot_sources import list_mugshot_sources as _ms_list

    _RB_SOURCE_OPTIONS = _ms_source_labels(include_unavailable=True)
    _RB_AVAILABLE_SOURCE_IDS = frozenset(
        s.id for s in _ms_list(available_only=True)
    )
except Exception:
    _RB_SOURCE_OPTIONS = [
        ("recentlybooked", "RecentlyBooked"),
        ("mugshotscom", "Mugshots.com"),
        ("bustednewspaper", "Busted Newspaper (unavailable)"),
    ]
    _RB_AVAILABLE_SOURCE_IDS = frozenset({"recentlybooked", "mugshotscom"})

_RB_SOURCE_LABELS = [label for _, label in _RB_SOURCE_OPTIONS]
_RB_SOURCE_BY_LABEL = {label: sid for sid, label in _RB_SOURCE_OPTIONS}
# Live Feed: check available hosts by default (not SSL-blocked BN).
_RB_LIVE_DEFAULT_SOURCES = frozenset(_RB_AVAILABLE_SOURCE_IDS)
_BN_UNAVAILABLE_HINT = (
    "Busted Newspaper unavailable (SSL) — cannot fix in-app right now."
)

_RB_LIVE_POLL_MS = 60000
