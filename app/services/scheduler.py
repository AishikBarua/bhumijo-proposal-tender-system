"""Background job bootstrap: fires app.services.pipeline.run_pipeline_check() on an
interval (Stages 1-4), independent of any HTTP request. Two properties from the
original design are load-bearing and must survive any future change here:

1. The scheduled job creates its OWN SessionLocal() rather than reusing a
   request-scoped session - it doesn't run inside a request at all.
2. It calls run_pipeline_check() directly (a plain function call), never over HTTP -
   there is no session, no login, nothing for auth to intercept. The job must keep
   firing whether or not anyone is logged in or has a browser open.

start_scheduler() also runs the other startup-time bootstrap that has nowhere more
specific to live (the one-off App Password DB migration, the startup status log) since
it was already sequenced together with scheduling in the original app.main.lifespan.
"""
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app import config
from app.database import SessionLocal
from app.models import EmailSettings
from app.services import pipeline
from app.services.credentials import clear_db_app_password_if_env_configured
from app.services.notify import notify_after_run

logger = logging.getLogger("tender_agent")

SCHEDULER_JOB_ID = "email_pipeline_check"
scheduler = BackgroundScheduler()


def _run_scheduled_check():
    # run_pipeline_check() already logs its own result (success summary at INFO, or the
    # error at ERROR) - see services.pipeline. This catch is a safety net for anything
    # that escapes that (e.g. the DB session itself failing to open), not the normal path.
    db = SessionLocal()
    try:
        settings = db.query(EmailSettings).first()
        if settings and settings.enabled:
            result = pipeline.run_pipeline_check(db)
            notify_after_run(db, settings, result)
    except Exception as e:
        logger.error("scheduled pipeline check failed unexpectedly: %s", e, exc_info=True)
    finally:
        db.close()


def reschedule(settings: EmailSettings) -> None:
    """(Re)adds the periodic background job to match current enabled/interval settings.
    Called at startup and again whenever Email settings are saved."""
    if scheduler.get_job(SCHEDULER_JOB_ID):
        scheduler.remove_job(SCHEDULER_JOB_ID)
    if settings and settings.enabled:
        scheduler.add_job(
            _run_scheduled_check, "interval",
            minutes=settings.check_interval_minutes or 15,
            id=SCHEDULER_JOB_ID,
        )


def _log_startup(settings) -> None:
    app_password_env = config.IMAP_APP_PASSWORD or config.GMAIL_APP_PASSWORD
    email_configured = bool(settings and settings.imap_email and
                             (app_password_env or settings.imap_app_password))
    job = scheduler.get_job(SCHEDULER_JOB_ID)
    if job:
        interval = settings.check_interval_minutes if settings else None
        job_status = f"registered, every {interval} min"
    else:
        job_status = "NOT registered (automatic checking is disabled in Email settings)"
    logger.info(
        "startup: port=%s anthropic_api_key=%s imap_host=%s imap_port=%s imap_app_password=%s "
        "email_settings=%s scheduler_job=%s",
        config.SERVER_PORT,
        "present" if config.ANTHROPIC_API_KEY else "MISSING",
        config.IMAP_HOST,
        config.IMAP_PORT,
        "present (env)" if app_password_env else "MISSING",
        "configured" if email_configured else "NOT configured",
        job_status,
    )


def start_scheduler(app) -> None:
    """Called once from app.main's lifespan on startup. `app` is accepted (unused for
    now) so the call site reads as "start the scheduler for this app" and to leave room
    for app.state wiring later without changing the call site."""
    db = SessionLocal()
    try:
        settings = db.query(EmailSettings).first()
        clear_db_app_password_if_env_configured(db, settings)
        reschedule(settings)
        _log_startup(settings)
    finally:
        db.close()
    scheduler.start()


def stop_scheduler() -> None:
    scheduler.shutdown(wait=False)
