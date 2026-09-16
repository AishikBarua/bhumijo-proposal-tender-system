"""
Deadline reminders — email before a proposal or grant closes.

The reminder logic is here and testable. Sending is deliberately left as a
stub until you tell me which mail account to use; until then it logs what it
would have sent, which is useful on its own.
"""

from __future__ import annotations

from datetime import date

from ..config import get_logger
from ..services import grant_service, metrics

log = get_logger("jobs.deadlines")

REMIND_AT_DAYS = (14, 7, 3, 1)


def build_digest(today: date | None = None) -> dict:
    today = today or date.today()
    proposals = [
        p for p in metrics.upcoming_deadlines(max(REMIND_AT_DAYS), today)
        if p["days_remaining"] in REMIND_AT_DAYS
    ]
    grants = [
        g for g in grant_service.closing_soon(max(REMIND_AT_DAYS), today)
        if g["days_remaining"] in REMIND_AT_DAYS
    ]
    overdue = metrics.overdue()

    return {
        "date": today.isoformat(),
        "proposals_closing": proposals,
        "grants_closing": grants,
        "overdue_proposals": overdue,
        "anything_to_send": bool(proposals or grants or overdue),
    }


def render_text(digest: dict) -> str:
    lines = [f"Bhumijo deadlines — {digest['date']}", ""]

    if digest["proposals_closing"]:
        lines.append("Proposals closing soon")
        for p in digest["proposals_closing"]:
            lines.append(
                f"  {p['days_remaining']:>2}d  {p['close_date']}  "
                f"[{p['entity_code'] or '--'}] {p['title'][:60]}"
            )
        lines.append("")

    if digest["grants_closing"]:
        lines.append("Grant programmes closing soon")
        for g in digest["grants_closing"]:
            lines.append(
                f"  {g['days_remaining']:>2}d  {g['closing_date']}  "
                f"{g['name'][:50]} ({g['investor'][:30]})"
            )
        lines.append("")

    if digest["overdue_proposals"]:
        lines.append("Past their close date with no result recorded")
        for p in digest["overdue_proposals"][:20]:
            lines.append(
                f"  {p['days_overdue']:>3}d overdue  {p['close_date']}  {p['title'][:60]}"
            )
        lines.append("")

    if not digest["anything_to_send"]:
        lines.append("Nothing closing in the next two weeks.")

    return "\n".join(lines)


def run(today: date | None = None) -> dict:
    digest = build_digest(today)
    text = render_text(digest)

    # TODO: send by email once the mail account is decided.
    # Until then the digest is logged, which already beats having nothing.
    for line in text.splitlines():
        log.info("%s", line)

    return digest


if __name__ == "__main__":
    run()
