"""RecentlyBooked Full Scrape per-row UI append and import helper."""
from __future__ import annotations

import threading
from typing import Any, Dict, Optional, Set

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
        self,
        row,
        *,
        eth,
        n,
        counters,
        workers,
        source_label,
        scrape_loc: str = "",
    ) -> None:
        # Always keep scraped rows in the session buffer so Hide no photo/race
        # toggles can show/hide them. (Previously no-photo rows were discarded
        # here, so unchecking Hide no photo had no effect.)
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
        loc = scrape_loc or str(row.get("_scrape_loc") or "")
        loc_bit = f" · {loc}" if loc else ""
        self.rb_full_status.configure(
            text=(
                f"{len(self._rb_full_records)}/{len(self._rb_full_all)} shown"
                f"{loc_bit} · "
                f"+{counters['imported']} imported · {counters['skipped']} skipped · "
                f"{counters['rejected']} no-photo dropped · {workers}t · {mode}"
            )
        )
        if n == 1 or n % 10 == 0:
            self.log_full(
                f"{source_label}: #{n}"
                + (f" @ {loc}" if loc else "")
                + f" · +{counters['imported']} imported, "
                f"{counters['rejected']} no-photo dropped, {workers} threads"
            )

    def _rb_full_set_progress(
        self,
        *,
        source_label: str,
        count: int,
        workers: int,
        counters: Dict[str, int],
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        loc = ""
        if isinstance(context, dict):
            loc = str(context.get("label") or "")
            if not loc:
                st = context.get("state") or ""
                co = context.get("county") or ""
                pg = context.get("page") or ""
                src = context.get("source") or ""
                bits = [str(x) for x in (src, f"{st}/{co}".strip("/"), f"p{pg}" if pg else "") if x]
                loc = " · ".join(bits)
        if loc:
            self._rb_full_last_loc = loc
        else:
            loc = str(getattr(self, "_rb_full_last_loc", "") or "")
        loc_bit = f" · {loc}" if loc else ""
        hide_race, hide_photo = self._rb_full_filter_flags()
        mode = self._rb_filter_mode_text(
            hide_no_race=hide_race, hide_no_photo=hide_photo
        )
        self.rb_full_status.configure(
            text=(
                f"Scraping{loc_bit} · {count} fetched · "
                f"+{counters.get('imported', 0)} imported · "
                f"{counters.get('rejected', 0)} no-photo · {workers}t · {mode}"
            )
        )
        self.log_full(
            f"{source_label}: scraping{loc_bit} · {count} record(s) fetched"
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
