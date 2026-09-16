"""A weekly summary of what moved — built on the audit log."""

from __future__ import annotations

from datetime import date, timedelta

from ..config import get_logger
from ..database.repositories.base import fetch_all
from ..services import metrics

log = get_logger("jobs.weekly")


def build(week_ending: date | None = None) -> dict:
    end = week_ending or date.today()
    start = end - timedelta(days=7)

    changes = fetch_all(
        """
        SELECT action, record_type, COUNT(*) AS n
        FROM audit_log
        WHERE occurred_at >= ?
        GROUP BY action, record_type
        ORDER BY n DESC
        """,
        (start.isoformat(),),
    )
    who = fetch_all(
        """
        SELECT username, COUNT(*) AS n FROM audit_log
        WHERE occurred_at >= ? GROUP BY username ORDER BY n DESC
        """,
        (start.isoformat(),),
    )

    return {
        "week_start": start.isoformat(),
        "week_end": end.isoformat(),
        "activity": changes,
        "by_person": who,
        "summary": metrics.summary(),
        "deadlines_next_30": metrics.upcoming_deadlines(30),
        "data_quality": metrics.data_quality(),
    }


def run() -> dict:
    digest = build()
    log.info(
        "weekly digest %s to %s: %d activity group(s), %d proposal(s) closing in 30 days",
        digest["week_start"], digest["week_end"],
        len(digest["activity"]), len(digest["deadlines_next_30"]),
    )
    return digest


if __name__ == "__main__":
    run()
