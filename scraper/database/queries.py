"""Query helpers for arrests."""
from __future__ import annotations

from scraper.database.queries_search import QuerySearchMixin
from scraper.database.queries_stats import QueryStatsMixin


class QueryMixin(QuerySearchMixin, QueryStatsMixin):
    """Public arrest query surface (search + stats + iteration)."""


__all__ = ["QueryMixin"]
