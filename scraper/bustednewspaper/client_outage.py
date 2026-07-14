"""Busted Newspaper outage messages and error helpers."""
from __future__ import annotations

import requests

# Human-readable outage blurb shown in the GUI / logs.
BN_SSL_OUTAGE_MSG = (
    "Busted Newspaper is unavailable (SSL/TLS or remote disconnect). "
    "Cannot be fixed in-app right now — use RecentlyBooked only."
)
# Alias used in UI copy.
BN_OUTAGE_MSG = BN_SSL_OUTAGE_MSG


class BustedNewspaperUnavailable(RuntimeError):
    """Raised when BN cannot be reached due to a known environment outage."""


def is_hard_outage(exc: BaseException) -> bool:
    """True for SSL/TLS or remote-close failures that we will not thrash on.

    BN currently dies with SSLError and/or RemoteDisconnected before any
    HTTP response. Retrying does not help in this environment.
    """
    if isinstance(exc, requests.exceptions.SSLError):
        return True
    name = type(exc).__name__.lower()
    if "ssl" in name:
        return True
    msg = str(exc).lower()
    markers = (
        "ssl",
        "tls",
        "certificate",
        "handshake",
        "wrong version number",
        "sslv3",
        "tlsv1",
        "unexpected_eof_while_reading",
        "eof occurred in violation of protocol",
        # Remote end closes during TLS/connect — same practical outage.
        "remotedisconnected",
        "connection aborted",
        "remote end closed connection without response",
    )
    return any(m in msg for m in markers)


def is_transient(exc: BaseException) -> bool:
    if is_hard_outage(exc):
        return False
    if isinstance(exc, requests.Timeout):
        return True
    msg = str(exc).lower()
    markers = (
        "read timed out",
        "timed out",
        "temporarily unavailable",
        "10054",
        "10053",
        "forcibly closed",
        "connection reset",
        "broken pipe",
    )
    return any(m in msg for m in markers)
