"""Arrest search query helpers."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from scraper.database.constants import _escape_like


class QuerySearchMixin:
    def search_by_name(
        self,
        name: str,
        state: Optional[str] = None,
        race: Optional[str] = None,
        charge_category: Optional[str] = None,
        source_system: Optional[str] = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        return self.search_records(
            name=name,
            state=state,
            race=race,
            charge_category=charge_category,
            source_system=source_system,
            limit=limit,
            offset=offset,
        )

    def search_records(
        self,
        *,
        name: Optional[str] = None,
        state: Optional[str] = None,
        race: Optional[str] = None,
        likely_ethnicity: Optional[str] = None,
        likely_ethnicity_in: Optional[List[str]] = None,
        ethnicity_review: Optional[str] = None,
        charge_category: Optional[str] = None,
        source_system: Optional[str] = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        limit = max(0, int(limit))
        offset = max(0, int(offset))
        q = "SELECT * FROM arrests WHERE 1=1"
        params: List[Any] = []
        if name and str(name).strip():
            esc = _escape_like(str(name).strip())
            term = f"%{esc}%"
            q += (
                " AND (full_name LIKE ? ESCAPE '\\' OR first_name LIKE ? ESCAPE '\\' "
                "OR last_name LIKE ? ESCAPE '\\')"
            )
            params.extend([term, term, term])
        if state and state.upper() != "ALL":
            q += " AND UPPER(COALESCE(state, '')) = UPPER(?)"
            params.append(state)
        if race and str(race).strip().lower() not in ("", "all", "*"):
            from scraper.searcher import format_race_label

            # Match by merged display label so grouped categories (e.g.
            # Other/Unknown, White) select every underlying raw variant.
            target_label = format_race_label(str(race).strip())
            raw_rows = self._conn.execute(
                """
                SELECT DISTINCT race FROM arrests
                WHERE race IS NOT NULL AND TRIM(race) != ''
                """
            ).fetchall()
            matched = [
                str(r["race"])
                for r in raw_rows
                if r and r["race"] and format_race_label(str(r["race"])) == target_label
            ]
            include_null = format_race_label("") == target_label
            if include_null:
                if matched:
                    ph = ",".join("?" * len(matched))
                    q += (
                        " AND (race IS NULL OR TRIM(race) = '' "
                        f"OR TRIM(race) IN ({ph}))"
                    )
                    params.extend(matched)
                else:
                    q += " AND (race IS NULL OR TRIM(race) = '')"
            elif matched:
                ph = ",".join("?" * len(matched))
                q += f" AND TRIM(race) IN ({ph})"
                params.extend(matched)
            else:
                q += " AND 0"
        if likely_ethnicity_in is not None:
            vals = [
                str(v).strip()
                for v in (likely_ethnicity_in or [])
                if v is not None and str(v).strip()
            ]
            if not vals:
                q += " AND 0"
            else:
                # Exact match or prefix (e.g. Indian → Indian (high_confidence),
                # European → European (english)). Escape LIKE metacharacters.
                parts: List[str] = []
                for v in vals:
                    low = v.lower()
                    esc = _escape_like(low)
                    parts.append(
                        "("
                        "LOWER(TRIM(COALESCE(likely_ethnicity, ''))) = ? "
                        "OR LOWER(TRIM(COALESCE(likely_ethnicity, ''))) "
                        "LIKE ? ESCAPE '\\' "
                        "OR LOWER(TRIM(COALESCE(likely_ethnicity, ''))) "
                        "LIKE ? ESCAPE '\\'"
                        ")"
                    )
                    params.extend([low, f"{esc} %", f"{esc}(%"])
                q += " AND (" + " OR ".join(parts) + ")"
        elif likely_ethnicity and str(likely_ethnicity).strip().lower() not in (
            "",
            "all",
            "*",
        ):
            actual = str(likely_ethnicity).strip()
            low = actual.lower()
            if low in ("unset", "none", "(unset)"):
                # Unset is not offered in Browse UI; keep for API callers only.
                q += (
                    " AND (likely_ethnicity IS NULL OR TRIM(likely_ethnicity) = '')"
                )
            else:
                esc = _escape_like(low)
                q += (
                    " AND ("
                    "LOWER(TRIM(COALESCE(likely_ethnicity, ''))) = ? "
                    "OR LOWER(TRIM(COALESCE(likely_ethnicity, ''))) "
                    "LIKE ? ESCAPE '\\' "
                    "OR LOWER(TRIM(COALESCE(likely_ethnicity, ''))) "
                    "LIKE ? ESCAPE '\\'"
                    ")"
                )
                params.extend([low, f"{esc} %", f"{esc}(%"])
        if charge_category and str(charge_category).lower() not in ("all", "", "*"):
            q += " AND LOWER(COALESCE(charge_category, '')) = LOWER(?)"
            params.append(charge_category)
        if source_system and str(source_system).lower() not in ("all", "", "*"):
            q += " AND LOWER(COALESCE(source_system, '')) = LOWER(?)"
            params.append(source_system)
        # Review status lives in JSON flags — filter in Python.
        # When a review filter is active, always load the full match set
        # (then apply limit), so a small LIMIT does not hide later rows.
        review = (ethnicity_review or "").strip().lower()
        review_active = bool(review and review not in ("all", "*", ""))
        if review_active or not limit:
            q += " ORDER BY arrest_date DESC, last_name ASC"
            if offset:
                q += " LIMIT -1 OFFSET ?"
                params.append(offset)
        else:
            q += " ORDER BY arrest_date DESC, last_name ASC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        rows = [dict(r) for r in self._conn.execute(q, params).fetchall()]
        if review_active:
            from scraper.searcher import ethnicity_review_verdict

            filtered = []
            for rec in rows:
                verdict = ethnicity_review_verdict(rec)
                if review in ("unreviewed", "none", "unset"):
                    if not verdict:
                        filtered.append(rec)
                elif verdict == review:
                    filtered.append(rec)
                if limit and len(filtered) >= limit:
                    break
            rows = filtered
        elif limit and len(rows) > limit:
            rows = rows[:limit]
        return rows
