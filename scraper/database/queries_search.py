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
        if likely_ethnicity and str(likely_ethnicity).strip().lower() not in (
            "",
            "all",
            "*",
        ):
            actual = str(likely_ethnicity).strip()
            if actual.lower() in ("unset", "none", "(unset)"):
                q += (
                    " AND (likely_ethnicity IS NULL OR TRIM(likely_ethnicity) = '')"
                )
            else:
                q += " AND LOWER(COALESCE(likely_ethnicity, '')) = LOWER(?)"
                params.append(actual)
        if charge_category and str(charge_category).lower() not in ("all", "", "*"):
            q += " AND LOWER(COALESCE(charge_category, '')) = LOWER(?)"
            params.append(charge_category)
        if source_system and str(source_system).lower() not in ("all", "", "*"):
            q += " AND LOWER(COALESCE(source_system, '')) = LOWER(?)"
            params.append(source_system)
        # Over-fetch when filtering review status in Python (JSON flags).
        review = (ethnicity_review or "").strip().lower()
        fetch_limit = limit
        if review and review not in ("all", "*", ""):
            fetch_limit = max(limit * 5, 5000) if limit else 0
        if fetch_limit:
            q += " ORDER BY arrest_date DESC, last_name ASC LIMIT ? OFFSET ?"
            params.extend([fetch_limit, offset])
        else:
            q += " ORDER BY arrest_date DESC, last_name ASC"
            if offset:
                q += " LIMIT -1 OFFSET ?"
                params.append(offset)
        rows = [dict(r) for r in self._conn.execute(q, params).fetchall()]
        if review and review not in ("all", "*", ""):
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
