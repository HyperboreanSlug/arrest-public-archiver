"""RecentlyBooked Full Scrape background worker."""
from __future__ import annotations

import threading
import time as _time
from typing import Any, Dict

from scraper.database import Database
from scraper.searcher import ArrestSearcher

from .constants import _RB_AVAILABLE_SOURCE_IDS
from .full_scrape_ui import _full_import_row


class RbFullScrapeWorkerMixin:
    def _rb_full_scrape_worker(self, cfg: Dict[str, Any]) -> None:
        source_id = cfg["source_id"]
        source_label = cfg["source_label"]
        workers = cfg["workers"]
        counters = {"imported": 0, "skipped": 0, "rejected": 0}
        scrape_warning = None
        import_lock = threading.Lock()
        try:
            eth = ArrestSearcher(cfg["db_path"]).ethnic_db
            self._rb_full_eth = eth
            db = Database(cfg["db_path"])
            try:
                purge_ids = (
                    list(_RB_AVAILABLE_SOURCE_IDS)
                    if source_id == "all"
                    else [source_id]
                )
                for sid in purge_ids:
                    try:
                        purged = db.delete_arrests_without_real_photos(
                            source_system=sid
                        )
                        if purged:
                            self.log(
                                f"Full scrape: deleted {purged} "
                                f"{sid} arrests without a real photo."
                            )
                    except Exception as exc:
                        self.log(f"Full scrape purge ({sid}) skipped: {exc}")
                known = db.existing_source_urls()

                def on_record(rec: Dict[str, Any], n: int) -> None:
                    row = dict(rec)
                    err = _full_import_row(row, db, known, counters, import_lock)
                    if err:
                        self.after(
                            0,
                            lambda e=err, u=str(row.get("source_url") or ""): self.log(
                                f"{source_label} store failed ({u}): {e}"
                            ),
                        )
                    self.after(
                        0,
                        lambda r=row, nn=n: self._rb_full_ui_append(
                            r,
                            eth=eth,
                            n=nn,
                            counters=counters,
                            workers=workers,
                            source_label=source_label,
                        ),
                    )

                _prog_t = [0.0]

                def on_progress(count, _total=None):
                    now = _time.time()
                    if now - _prog_t[0] < 3.0:
                        return
                    _prog_t[0] = now
                    self.after(
                        0,
                        lambda c=count: self.log(
                            f"{source_label}: working… {c} record(s) fetched"
                        ),
                    )

                try:
                    self._rb_full_run_scraper(
                        source_id=source_id,
                        state=cfg["state"],
                        county=cfg["county"],
                        scrape_all=cfg["scrape_all"],
                        delay=cfg["delay"],
                        workers=workers,
                        with_photos=cfg["with_photos"],
                        with_html=cfg["with_html"],
                        known=known,
                        db=db,
                        on_record=on_record,
                        on_progress=on_progress,
                    )
                except Exception as scrape_exc:
                    scrape_warning = self._rb_full_scrape_error_msg(scrape_exc)
                    self.log(
                        f"{source_label}: scrape interrupted ({scrape_warning}). "
                        f"Keeping {counters['imported']} imported so far."
                    )
                try:
                    if source_id == "all":
                        dret = db.remove_cross_source_duplicates(
                            dry_run=False,
                            merge_fields=True,
                            source_systems=list(_RB_AVAILABLE_SOURCE_IDS),
                        )
                    else:
                        dret = db.remove_name_dob_photo_duplicates(
                            dry_run=False,
                            merge_fields=True,
                            source_system=source_id,
                        )
                    _removed = int(dret.get("deleted") or 0)
                    if _removed:
                        self.log(
                            f"Full scrape dedupe: removed {_removed} duplicate row(s)."
                        )
                except Exception as exc:
                    self.log(f"Full scrape dedupe skipped: {exc}")
            finally:
                db.close()

            msg = (
                f"{source_label} full scrape done: "
                f"{len(self._rb_full_records)}/{len(self._rb_full_all)} shown, "
                f"+{counters['imported']} imported, {counters['skipped']} skipped, "
                f"{counters['rejected']} no-photo dropped ({workers} threads)."
            )
            if scrape_warning:
                msg += f" · interrupted: {scrape_warning}"
            self.log(msg)
            self.after(0, lambda: self.rb_full_status.configure(text=msg))
            self.after(0, self._refresh_db_status)
        except Exception as e:
            self.log(f"{source_label} scrape failed: {e}")
            self.after(
                0,
                lambda: self.rb_full_status.configure(text=f"Failed: {e}"),
            )
