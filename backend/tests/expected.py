"""
What the numbers *should* be, read from the data rather than typed in.

The tests used to assert "179 proposals", "52 in FM", "46 won". Those were
true on 1 September and false by the 7th, because people kept adding
proposals — so six tests failed while nothing was actually broken.

A test that hardcodes a count stops testing the software and starts testing
the calendar. These helpers read the truth from the database, so the tests
check the thing that matters: that the API and the database agree.
"""

from __future__ import annotations

from ..database.repositories import proposal_repo
from ..database.repositories.base import scalar
from ..models.enums import LOST_RESULTS, WON_RESULTS


def total_proposals() -> int:
    return scalar("SELECT COUNT(*) FROM proposals") or 0


def total_grants() -> int:
    return scalar("SELECT COUNT(*) FROM grant_programmes") or 0


def total_clients() -> int:
    return scalar("SELECT COUNT(*) FROM clients") or 0


def proposals_in(entity_code: str) -> int:
    return scalar(
        "SELECT COUNT(*) FROM proposals WHERE entity_code = ?", (entity_code,)
    ) or 0


def won_and_lost() -> tuple[int, int]:
    rows = proposal_repo.list_all()
    won = sum(1 for r in rows if r.get("result") in WON_RESULTS)
    lost = sum(1 for r in rows if r.get("result") in LOST_RESULTS)
    return won, lost


def priced_and_unpriced() -> tuple[int, int]:
    priced = scalar("SELECT COUNT(*) FROM proposals WHERE value_amount IS NOT NULL") or 0
    return priced, total_proposals() - priced


def summary_line() -> str:
    return (f"{total_proposals()} proposals, {total_grants()} grants, "
            f"{total_clients()} clients")
