"""
Runs the no-API check on a timer.

Separate from the AI agent's scheduler on purpose: if you never set an API
key, this one still runs, and if you later do, the two are independent.
"""

from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler

from app.database import SessionLocal
from app.models import EmailSettings
from app.services.credentials import get_app_password
from backend.config import get_logger

from .pipeline import run_check, summary_message

log = get_logger("agent_free.scheduler")

_scheduler: BackgroundScheduler | None = None
JOB_ID = "agent_free_check"


def _tick() -> None:
    db = SessionLocal()
    try:
        counters = run_check(db)
        log.info("scheduled check: %s", summary_message(counters))
    except Exception:  # noqa: BLE001 — a failed run must not kill the scheduler
        log.exception("the no-API check failed")
    finally:
        db.close()


def start() -> None:
    global _scheduler
    if _scheduler is not None:
        return

    db = SessionLocal()
    try:
        settings_row = db.query(EmailSettings).first()
        minutes = (settings_row.check_interval_minutes if settings_row else 15) or 15
        # Same reason as in pipeline.run_check: the password is an environment
        # variable, so the database column is not what decides this.
        configured = bool(settings_row and settings_row.imap_email
                          and get_app_password(settings_row))
    finally:
        db.close()

    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(_tick, "interval", minutes=minutes, id=JOB_ID)
    _scheduler.start()

    if configured:
        log.info("no-API agent: checking the mailbox every %d minutes", minutes)
    else:
        # Said plainly, because otherwise "it isn't finding anything" looks
        # like a bug rather than a missing password.
        log.info("no-API agent: timer running every %d minutes, but the mailbox "
                 "is not configured yet — it will find nothing until the email "
                 "address and app password are set under Email settings",
                 minutes)


def stop() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
