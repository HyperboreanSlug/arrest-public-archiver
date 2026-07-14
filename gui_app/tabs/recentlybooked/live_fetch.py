"""RecentlyBooked Live Feed multi-source fetch + import."""
from __future__ import annotations

from typing import Any, Dict, List, Set

from scraper.database import Database


def _live_import_done(
    done: Dict[str, Any],
    db: Database,
    known: Set[str],
    counters: Dict[str, int],
    new_rows: List[Dict[str, Any]],
    has_photo,
) -> None:
    try:
        result = db.import_records(
            [done],
            skip_existing_urls=True,
            skip_identity_duplicates=True,
            require_photo=True,
        )
        counters["imported"] += int(result.get("imported") or 0)
        counters["skipped"] += int(result.get("skipped") or 0)
        counters["rejected"] += int(result.get("rejected_no_photo") or 0)
        url = str(done.get("source_url") or "")
        if url:
            known.add(url)
        if not done.get("id") and url:
            found = db._conn.execute(
                "SELECT id FROM arrests WHERE source_url = ? "
                "ORDER BY id DESC LIMIT 1",
                (url,),
            ).fetchone()
            if found:
                done["id"] = int(found[0])
    except Exception as exc:
        done["scrape_error"] = (
            f"{done.get('scrape_error')}; import: {exc}"
            if done.get("scrape_error")
            else f"import: {exc}"
        )
    if has_photo(done) or done.get("id"):
        new_rows.append(done)


class RbLiveFetchMixin:
    def _rb_live_fetch(
        self, sources, known, counters, new_rows, errors, *,
        delay, bn_delay, incremental,
    ) -> None:
        db = Database(self.db_path)
        try:
            if not incremental:
                for src in sources:
                    try:
                        purged = db.delete_arrests_without_real_photos(
                            source_system=src
                        )
                        if purged:
                            self.log_live(
                                f"Live feed: deleted {purged} "
                                f"{src} arrests without a real photo."
                            )
                    except Exception as exc:
                        self.log_live(f"Live feed purge ({src}) skipped: {exc}")

            from scraper.mugshot_sources import IdentityIndex, MultiSourceOrchestrator

            identity = IdentityIndex()
            identity.seed_from_db(db)
            for u in known:
                identity.add_url(u)
            orch = MultiSourceOrchestrator(
                sources, delay=max(delay, bn_delay * 0.5), identity=identity
            )

            def on_live_rec(rec: Dict[str, Any], n: int) -> None:
                _live_import_done(
                    dict(rec), db, known, counters, new_rows, self._rb_has_photo
                )
                if n == 1 or n % 5 == 0:
                    src = rec.get("source_system") or "?"
                    self.log_live(
                        f"Live feed ({src}): #{n} · "
                        f"+{counters['imported']} imported · "
                        f"{counters['rejected']} no-photo dropped…"
                    )

            multi = orch.scrape_live(
                row_limit_per_source=(12 if incremental else 24),
                skip_existing_urls=known,
                with_photos=True,
                record_cb=on_live_rec,
            )
            for sid, err in (multi.errors or {}).items():
                errors.append(f"{sid}: {err}")
                self.log_live(f"Live feed {sid} skipped: {err}")
            if multi.skipped_identity:
                self.log_live(
                    f"Live feed: skipped {multi.skipped_identity} "
                    "cross-host identity duplicate(s)."
                )
            for sid, n in (multi.by_source or {}).items():
                self.log_live(f"Live feed {sid}: {n} record callback(s).")
            try:
                dret = db.remove_cross_source_duplicates(
                    dry_run=False,
                    merge_fields=True,
                    source_systems=list(sources) or None,
                )
                _removed = int(dret.get("deleted") or 0)
                if _removed:
                    self.log_live(
                        f"Live feed cross-source dedupe: removed "
                        f"{_removed} duplicate row(s)."
                    )
            except Exception as exc:
                self.log_live(f"Live feed cross-source dedupe skipped: {exc}")
        finally:
            db.close()
