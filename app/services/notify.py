"""Sends one status email after every scheduled pipeline run - success, "nothing
found", or failure alike. This is deliberate, not noise: if the email only arrived
when there was news, silence would be ambiguous (nothing new vs. the app died
silently). Sending every time means a missing email is itself the failure signal.

Reuses the IMAP address/App Password already used for fetch (app.services.pipeline) -
no separate SMTP credentials to configure. The App Password itself comes from
app.services.credentials.get_app_password (env var first, deprecated DB fallback
second) - see docs/SECURITY.md. SMTP host/port are configured (app.config.SMTP_HOST/
SMTP_PORT, currently Zoho) rather than hardcoded.
"""
import logging
import re
import smtplib
from email.mime.text import MIMEText

from sqlalchemy.orm import Session

from app.config import DASHBOARD_URL, SMTP_HOST, SMTP_PORT
from app.models import EmailSettings, Tender
from app.services.credentials import get_app_password

logger = logging.getLogger("tender_agent")


def notify_after_run(db: Session, settings: EmailSettings, result: dict) -> None:
    """Sends the status email for one pipeline run - called from both the scheduled job
    and the manual "Check now" route, so both go through the same body-building and
    error-swallowing logic. Never raises: a failed notification must not fail whatever
    just-completed pipeline run triggered it, so any error here is logged and dropped."""
    if not settings.notify_enabled:
        return
    try:
        if "error" in result:
            send_daily_summary(settings, summary_text="", error_text=result["error"])
        else:
            send_daily_summary(settings, summary_text=_build_run_body(db, result))
    except Exception as e:
        logger.error("notification email failed to send: %s", e, exc_info=True)


def _build_run_body(db: Session, result: dict) -> str:
    """The one-line summary plus per-tender detail for anything newly found this run."""
    from app.services.pipeline import summary_message  # deferred: avoids notify<->pipeline import-order coupling

    summary_line = summary_message(result)
    new_ids = result.get("new_tender_ids") or []
    if not new_ids:
        return summary_line

    tenders = db.query(Tender).filter(Tender.id.in_(new_ids)).all()
    lines = [summary_line, "", "New tenders:"]
    for t in tenders:
        fit = t.fit_score if t.fit_score is not None else "n/a"
        lines.append(f"- {t.title or '(untitled)'} | {t.organization or 'n/a'} | "
                     f"deadline: {t.deadline or 'n/a'} | fit score: {fit}")
    return "\n".join(lines)


def send_daily_summary(settings: EmailSettings, summary_text: str, error_text: str = None) -> None:
    """Sends the status email via SMTP_SSL (SMTP_HOST:SMTP_PORT - see app.config).
    Raises on any failure - callers must wrap this in try/except so a notification
    problem (bad credentials, network blip) never aborts the pipeline run itself."""
    app_password = get_app_password(settings)
    to_addr = (settings.notify_email or settings.imap_email or "").strip()
    if not to_addr or not settings.imap_email or not app_password:
        raise RuntimeError("notify: IMAP/SMTP credentials or recipient address not configured")

    if error_text:
        subject = "Tender Agent — FAILED"
        body = f"The scheduled tender check failed:\n\n{error_text}\n\n{DASHBOARD_URL}"
    else:
        new_count_match = re.search(r"(\d+) new", summary_text or "")
        new_count = int(new_count_match.group(1)) if new_count_match else 0
        subject = f"Tender Agent — {new_count} new tenders" if new_count else "Tender Agent — nothing new"
        body = f"{summary_text}\n\n{DASHBOARD_URL}"

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = settings.imap_email
    msg["To"] = to_addr

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
        server.login(settings.imap_email, app_password)
        server.sendmail(settings.imap_email, [to_addr], msg.as_string())
