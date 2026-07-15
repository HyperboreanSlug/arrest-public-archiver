"""RecentlyBooked Misclassify surname analysis worker."""
from __future__ import annotations

import threading

from gui_app.shared.record_sidebar import race_manual_override
from gui_app.tabs.browse.misclassify_constants import verification_label
from gui_app.widgets import tree_row_bind, tree_rows_reset
from scraper.charge_summary import summarize_charge
from scraper.searcher import ArrestSearcher

from .constants import _RB_SOURCE_OPTIONS


class RbMisclassifyAnalyzeMixin:
    def _rb_analyze(self):
        self.rb_mc_status.configure(text="Analyzing…")
        self.rb_mc_sidebar.clear("Analyzing…")
        race_filter = self._rb_mc_race_filter()
        review_q = self._rb_mc_review_query()
        # searcher uses unreviewed by default; None = all confirmation statuses
        review_arg = review_q if review_q is not None else "all"
        mugshot_sources = [sid for sid, _ in _RB_SOURCE_OPTIONS]

        def work():
            s = ArrestSearcher(self.db_path)
            persisted = 0
            dedupe_removed = 0
            rows = []
            base = 0
            try:
                db = s.db
                for src in mugshot_sources:
                    dedupe_result = db.remove_name_dob_photo_duplicates(
                        dry_run=False,
                        merge_fields=True,
                        source_system=src,
                    )
                    dedupe_removed += int(dedupe_result.get("deleted") or 0)
                if dedupe_removed:
                    self.log(
                        "RB misclassify dedupe: removed "
                        f"{dedupe_removed} duplicate row(s)."
                    )
                for src in mugshot_sources:
                    part, part_base = s.analyze_ethnicities(
                        source_system=src,
                        race=race_filter,
                        ethnicity_review=review_arg,
                        return_base_count=True,
                    )
                    rows.extend(part)
                    base += int(part_base or 0)
                rows.sort(key=lambda m: float(m.confidence or 0), reverse=True)
                for mc in rows:
                    rec = mc.record or {}
                    rid = rec.get("id")
                    assumed = (mc.likely_ethnicity or "").strip()
                    if rid is None or not assumed:
                        continue
                    if race_manual_override(rec):
                        continue
                    try:
                        s.db.update_arrest(
                            int(rid), {"likely_ethnicity": assumed}
                        )
                        persisted += 1
                    except Exception:
                        pass
            finally:
                s.close()

            def fill():
                self.rb_mc_tree.delete(*self.rb_mc_tree.get_children())
                tree_rows_reset(self.rb_mc_tree)
                self._rb_mc_records = []
                for mc in rows:
                    rec = dict(mc.record or {})
                    rec.setdefault("race", mc.expected_race)
                    if mc.likely_ethnicity:
                        rec["likely_ethnicity"] = mc.likely_ethnicity
                    if mc.confidence is not None:
                        rec["confidence"] = mc.confidence
                    self._rb_mc_records.append(rec)
                    name = (
                        f"{rec.get('first_name') or ''} {rec.get('last_name') or ''}"
                    ).strip() or rec.get("full_name") or "—"
                    item = self.rb_mc_tree.insert(
                        "",
                        "end",
                        values=(
                            name,
                            mc.expected_race,
                            mc.likely_ethnicity,
                            f"{mc.confidence:.2f}",
                            verification_label(rec),
                            summarize_charge(rec),
                            rec.get("state") or "",
                        ),
                    )
                    tree_row_bind(self.rb_mc_tree, item, rec)
                race_lbl = race_filter or "all races"
                conf_lbl = (
                    getattr(self, "rb_mc_review", None).get()
                    if getattr(self, "rb_mc_review", None)
                    else "Unverified"
                )
                msg = (
                    f"Surname analysis (mugshot sources, stated={race_lbl}, "
                    f"confirmation={conf_lbl}): "
                    f"{len(rows)} flags from {base} names"
                    + (
                        f" · deduped {dedupe_removed} duplicate(s)"
                        if dedupe_removed
                        else ""
                    )
                    + (
                        f" · {persisted} assumed races carried over."
                        if persisted
                        else "."
                    )
                )
                self.log(msg)
                self.rb_mc_status.configure(text=msg)
                if self._rb_mc_records:
                    first = self.rb_mc_tree.get_children()
                    if first:
                        self.rb_mc_tree.selection_set(first[0])
                        self.rb_mc_tree.focus(first[0])
                        self.rb_mc_sidebar.show(self._rb_mc_records[0])
                else:
                    self.rb_mc_sidebar.clear("No flags.")

            self.after(0, fill)

        threading.Thread(target=work, daemon=True).start()
