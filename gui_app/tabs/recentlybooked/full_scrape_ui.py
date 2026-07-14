"""RecentlyBooked Full Scrape per-row UI append and import helper."""
from __future__ import annotations

import threading
from typing import Any, Dict, Set

from scraper.database import Database


def _full_import_row(
    row: Dict[str, Any],
    db: Database,
    known: Set[str],
    counters: Dict[str, int],
    import_lock: threading.Lock,
) -> str | None:
    """Import one row. Returns error text on failure, else None."""
    try:
        with import_lock:
            result = db.import_records(
                [row],
                skip_existing_urls=True,
                skip_identity_duplicates=True,
                require_photo=True,
            )
            counters["imported"] += int(result.get("imported") or 0)
            counters["skipped"] += int(result.get("skipped") or 0)
            counters["rejected"] += int(result.get("rejected_no_photo") or 0)
            url = str(row.get("source_url") or "")
            if url and (result.get("imported") or result.get("skipped")):
                known.add(url)
            if not row.get("id") and url and result.get("imported"):
                found = db._conn.execute(
                    "SELECT id FROM arrests WHERE source_url = ? "
                    "ORDER BY id DESC LIMIT 1",
                    (url,),
                ).fetchone()
                if found:
                    row["id"] = int(found[0])
        return None
    except Exception as exc:
        err = f"import: {exc}"
        row["scrape_error"] = (
            f"{row.get('scrape_error')}; {err}" if row.get("scrape_error") else err
        )
        return err


class RbFullScrapeUiMixin:
    def _rb_full_ui_append(
        self, row, *, eth, n, counters, workers, source_label
    ) -> None:
        if not (self._rb_has_photo(row) or row.get("id")):
            self.rb_full_status.configure(
                text=(
                    f"{len(self._rb_full_records)}/{len(self._rb_full_all)} shown · "
                    f"+{counters['imported']} imported · {counters['skipped']} skipped · "
                    f"{counters['rejected']} no-photo dropped · {workers}t"
                )
            )
            return
        self._rb_full_all.append(row)
        hide_race, hide_photo = self._rb_full_filter_flags()
        visible = True
        if hide_race and not self._rb_has_race(row):
            visible = False
        if hide_photo and not self._rb_has_photo(row):
            visible = False
        if visible:
            self._rb_append_row(
                self.rb_full_tree,
                self._rb_full_records,
                row,
                eth=eth,
                sidebar=self.rb_full_sidebar,
                select_latest=(len(self._rb_full_records) == 1),
                status_label=None,
            )
        mode = self._rb_filter_mode_text(
            hide_no_race=hide_race, hide_no_photo=hide_photo
        )
        self.rb_full_status.configure(
            text=(
                f"{len(self._rb_full_records)}/{len(self._rb_full_all)} shown · "
                f"+{counters['imported']} imported · {counters['skipped']} skipped · "
                f"{counters['rejected']} no-photo dropped · {workers}t · {mode}"
            )
        )
        if n == 1 or n % 10 == 0:
            self.log(
                f"{source_label}: {n} scraped "
                f"(+{counters['imported']} imported, "
                f"{counters['rejected']} no-photo dropped, {workers} threads)"
            )

    @staticmethod
    def _rb_full_scrape_error_msg(scrape_exc: Exception) -> str:
        try:
            from scraper.bustednewspaper import (
                BN_SSL_OUTAGE_MSG,
                BustedNewspaperUnavailable,
            )

            if isinstance(scrape_exc, BustedNewspaperUnavailable) or (
                "ssl" in str(scrape_exc).lower() or "tls" in str(scrape_exc).lower()
            ):
                return BN_SSL_OUTAGE_MSG
            return str(scrape_exc)
        except Exception:
            return str(scrape_exc)
