"""
Win rate, pipeline and entity summaries.

These were computed in the browser, which meant every device could produce a
slightly different answer and none of them could be checked. Computed here
once, they are the same number for everyone and can be tested.
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any, Iterable

from ..database.repositories import proposal_repo, reference_repo
from ..models.common import days_until
from ..models.enums import DECIDED_RESULTS, LOST_RESULTS, WON_RESULTS


def _in_range(row: dict, start: str | None, end: str | None) -> bool:
    if not start and not end:
        return True
    stamp = row.get("close_date") or row.get("open_date")
    if not stamp:
        return False
    if start and stamp < start:
        return False
    if end and stamp > end:
        return False
    return True


def _filtered(
    entity_code: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> list[dict]:
    rows = proposal_repo.list_all(entity_code=entity_code)
    return [r for r in rows if _in_range(r, start, end)]


def summary(
    *,
    entity_code: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> dict[str, Any]:
    rows = _filtered(entity_code, start, end)
    total = len(rows)

    won = sum(1 for r in rows if r.get("result") in WON_RESULTS)
    lost = sum(1 for r in rows if r.get("result") in LOST_RESULTS)
    decided = won + lost
    pending = sum(1 for r in rows if not r.get("result"))

    value_won = sum(r["value_amount"] for r in rows
                    if r.get("result") in WON_RESULTS and r.get("value_amount"))
    value_total = sum(r["value_amount"] for r in rows if r.get("value_amount"))
    priced = sum(1 for r in rows if r.get("value_amount") is not None)

    return {
        "total": total,
        "won": won,
        "lost": lost,
        "pending": pending,
        "decided": decided,
        "win_rate": round(won / decided * 100, 1) if decided else None,
        "value_won": value_won or None,
        "value_total": value_total or None,
        # Honest about coverage: most records have no value, so any money
        # figure is based on a minority of them. Say so rather than imply
        # the total is complete.
        "priced_records": priced,
        "unpriced_records": total - priced,
    }


def by_status(**filters) -> dict[str, int]:
    rows = _filtered(**filters)
    counts = Counter(r.get("status") or "(blank)" for r in rows)
    return dict(counts.most_common())


def by_result(**filters) -> dict[str, int]:
    rows = _filtered(**filters)
    counts = Counter(r.get("result") or "(blank)" for r in rows)
    return dict(counts.most_common())


def by_entity(start: str | None = None, end: str | None = None) -> list[dict]:
    out = []
    for entity in reference_repo.entities():
        stats = summary(entity_code=entity["code"], start=start, end=end)
        out.append({
            "code": entity["code"],
            "name": entity["name"],
            **stats,
        })
    return out


def by_category(**filters) -> dict[str, int]:
    rows = _filtered(**filters)
    counts = Counter(
        (r.get("category_name") or r.get("original_category") or "(blank)") for r in rows
    )
    return dict(counts.most_common())


def upcoming_deadlines(within_days: int = 30, today: date | None = None) -> list[dict]:
    """Proposals closing soon that have not been decided yet."""
    today = today or date.today()
    out = []
    for row in proposal_repo.list_all():
        if row.get("result") in DECIDED_RESULTS:
            continue
        days = days_until(row.get("close_date"), today)
        if days is None or days < 0 or days > within_days:
            continue
        out.append({
            "id": row["id"],
            "title": row.get("title", ""),
            "entity_code": row.get("entity_code"),
            "client_name": row.get("client_name", ""),
            "close_date": row.get("close_date"),
            "days_remaining": days,
            "status": row.get("status", ""),
        })
    return sorted(out, key=lambda r: r["days_remaining"])


def overdue() -> list[dict]:
    """Past their close date, still undecided — invisible in the old system."""
    today = date.today()
    out = []
    for row in proposal_repo.list_all():
        if row.get("result") in DECIDED_RESULTS:
            continue
        days = days_until(row.get("close_date"), today)
        if days is None or days >= 0:
            continue
        out.append({
            "id": row["id"],
            "title": row.get("title", ""),
            "entity_code": row.get("entity_code"),
            "close_date": row.get("close_date"),
            "days_overdue": -days,
        })
    return sorted(out, key=lambda r: -r["days_overdue"])


def data_quality() -> dict[str, Any]:
    """
    How much of the data can actually be reported on. This is the figure that
    tells you whether a pipeline number means anything yet.
    """
    rows = proposal_repo.list_all()
    total = len(rows) or 1
    missing_value = sum(1 for r in rows if r.get("value_amount") is None)
    missing_category = sum(
        1 for r in rows if not (r.get("category_name") or r.get("original_category"))
    )
    missing_close = sum(1 for r in rows if not r.get("close_date"))
    missing_result = sum(1 for r in rows if not r.get("result"))

    return {
        "total": len(rows),
        "missing_value": missing_value,
        "missing_value_pct": round(missing_value / total * 100, 1),
        "missing_category": missing_category,
        "missing_close_date": missing_close,
        "missing_result": missing_result,
    }
