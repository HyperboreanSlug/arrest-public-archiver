"""SQLite Database composed of mixins."""
from __future__ import annotations

import threading
from typing import Optional

from scraper.database.backup import backup_database_file
from scraper.database.csv_io import CsvIoMixin
from scraper.database.dedupe import DedupeMixin
from scraper.database.deepface_scans import DeepfaceScanMixin, photo_fingerprint
from scraper.database.inserts import InsertMixin
from scraper.database.queries import QueryMixin
from scraper.database.schema import SchemaMixin


class Database(
    DeepfaceScanMixin,
    DedupeMixin,
    CsvIoMixin,
    InsertMixin,
    QueryMixin,
    SchemaMixin,
):
    """Public arrest/booking SQLite archive."""

    @classmethod
    def create_in_memory(cls) -> "Database":
        return cls(db_path=":memory:")


_db_singleton: Optional[Database] = None
_db_lock = threading.Lock()


def get_database(db_path: Optional[str] = None) -> Database:
    global _db_singleton
    if db_path is not None:
        return Database(db_path)
    with _db_lock:
        if _db_singleton is None:
            _db_singleton = Database()
        return _db_singleton


__all__ = [
    "Database",
    "get_database",
    "backup_database_file",
    "photo_fingerprint",
]
