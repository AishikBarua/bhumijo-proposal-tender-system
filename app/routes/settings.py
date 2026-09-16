from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session

from app.config import IMAP_HOST, IMAP_PORT
from app.database import get_db
from app.services import email_intake, pipeline
from app.services.credentials import get_app_password, is_app_password_configured
from app.services.email_settings_service import get_or_create_email_settings
from app.services.notify import notify_after_run
from app.services.scheduler import reschedule
from app.templating import templates

router = APIRouter()


def _context(request: Request, settings, result: str = None) -> dict:
    return {
        "request": request, "settings": settings, "result": result,
        "app_password_configured": is_app_password_configured(),
        "imap_host": IMAP_HOST, "imap_port": IMAP_PORT,
    }


@router.get("/email-settings", response_class=HTMLResponse)
def email_settings_page(request: Request, db: Session = Depends(get_db)):
    settings = get_or_create_email_settings(db)
    return templates.TemplateResponse("email_settings.html", _context(request, settings))


@router.post("/email-settings")
def update_email_settings(
    imap_email: str = Form(""),
    sender_filter: str = Form(""),
    sender_denylist: str = Form(""),
    enabled: str = Form(""),
    check_interval_minutes: str = Form("15"),
    notify_email: str = Form(""),
    notify_enabled: str = Form(""),
    db: Session = Depends(get_db),
):
    settings = get_or_create_email_settings(db)
    settings.imap_email = imap_email.strip() or None
    # The App Password field has been removed from this form entirely - it now comes
    # only from the IMAP_APP_PASSWORD environment variable (see app.config and
    # docs/SECURITY.md). Nothing here writes to settings.imap_app_password anymore.
    settings.sender_filter = sender_filter.strip() or None
    settings.sender_denylist = sender_denylist.strip() or None
    settings.enabled = enabled.lower() in ("on", "true", "1", "yes")
    settings.notify_email = notify_email.strip() or None
    settings.notify_enabled = notify_enabled.lower() in ("on", "true", "1", "yes")
    try:
        settings.check_interval_minutes = max(5, int(check_interval_minutes))
    except ValueError:
        settings.check_interval_minutes = 15
    db.commit()
    reschedule(settings)
    return RedirectResponse(url="/agent/email-settings", status_code=303)


@router.post("/email-settings/check-now", response_class=HTMLResponse)
def email_settings_check_now(request: Request, db: Session = Depends(get_db)):
    settings = get_or_create_email_settings(db)
    pipeline_result = pipeline.run_pipeline_check(db)
    result = pipeline.summary_message(pipeline_result)
    notify_after_run(db, settings, pipeline_result)
    return templates.TemplateResponse("email_settings.html", _context(request, settings, result))


@router.post("/email-settings/test-connection", response_class=HTMLResponse)
def email_settings_test_connection(request: Request, db: Session = Depends(get_db)):
    """Attempts an IMAP login only - no fetch, no AI calls - so a credential can be
    verified in isolation at zero cost."""
    settings = get_or_create_email_settings(db)
    app_password = get_app_password(settings)
    if not settings.imap_email or not app_password:
        result = "Email address or App Password not configured - see docs/SECURITY.md."
    else:
        try:
            email_intake.test_connection(settings.imap_email, app_password)
            result = f"Connected to {IMAP_HOST}:{IMAP_PORT} and logged in successfully."
        except Exception as e:
            result = str(e)
    return templates.TemplateResponse("email_settings.html", _context(request, settings, result))
