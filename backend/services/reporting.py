"""
Report building and exports — CSV now, DOC/PDF hooks ready.

The browser used to build these (buildNarrative, buildStatusSummary,
exportCSV). Doing it here means a report is the same whoever runs it.
"""

from __future__ import annotations

import csv
import io
from datetime import date
from typing import Any

from ..database.repositories import proposal_repo
from ..models.common import format_money
from ..models.proposal import to_legacy_dict
from . import metrics

CSV_COLUMNS = [
    ("id", "ID"),
    ("title", "Title"),
    ("entity", "Entity"),
    ("category", "Category"),
    ("client", "Client"),
    ("value", "Value"),
    ("responsible", "Responsible"),
    ("openDate", "Open date"),
    ("closeDate", "Close date"),
    ("status", "Status"),
    ("result", "Result"),
    ("contract", "Contract"),
    ("startDate", "Start date"),
    ("endDate", "End date"),
    ("remark", "Remark"),
]


def proposals_csv(**filters) -> str:
    rows = proposal_repo.list_all(**filters)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow([label for _, label in CSV_COLUMNS])
    for row in rows:
        legacy = to_legacy_dict(row)
        writer.writerow([legacy.get(key, "") for key, _ in CSV_COLUMNS])
    return buffer.getvalue()


def period_report(
    *,
    start: str | None = None,
    end: str | None = None,
    entity_code: str | None = None,
) -> dict[str, Any]:
    stats = metrics.summary(entity_code=entity_code, start=start, end=end)
    return {
        "generated_at": date.today().isoformat(),
        "period": {"start": start, "end": end},
        "entity_code": entity_code,
        "summary": stats,
        "by_status": metrics.by_status(entity_code=entity_code, start=start, end=end),
        "by_result": metrics.by_result(entity_code=entity_code, start=start, end=end),
        "by_category": metrics.by_category(entity_code=entity_code, start=start, end=end),
        "by_entity": metrics.by_entity(start=start, end=end) if not entity_code else None,
        "narrative": _narrative(stats, start, end),
        "data_quality": metrics.data_quality(),
    }


def _narrative(stats: dict, start: str | None, end: str | None) -> str:
    period = "all time"
    if start and end:
        period = f"{start} to {end}"
    elif start:
        period = f"since {start}"
    elif end:
        period = f"up to {end}"

    parts = [f"{stats['total']} proposals in the period ({period})."]

    if stats["decided"]:
        parts.append(
            f"{stats['won']} accepted and {stats['lost']} rejected out of "
            f"{stats['decided']} decided — a win rate of {stats['win_rate']}%."
        )
    else:
        parts.append("None have a recorded result yet.")

    if stats["pending"]:
        parts.append(f"{stats['pending']} are still awaiting a result.")

    if stats["value_won"]:
        parts.append(
            f"Accepted work carries {format_money(stats['value_won'])}, but this "
            f"covers only {stats['priced_records']} of {stats['total']} records — "
            f"{stats['unpriced_records']} have no value recorded, so treat any "
            f"total as a floor, not the real figure."
        )
    elif stats["unpriced_records"]:
        parts.append(
            f"No value figure can be given: {stats['unpriced_records']} of "
            f"{stats['total']} records have no value recorded."
        )

    return " ".join(parts)
