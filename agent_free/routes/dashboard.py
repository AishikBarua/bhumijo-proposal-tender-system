"""
The screens for the no-API agent, at /agent-free.

Routes only — no keyword logic and no database queries beyond fetching what
a page displays. The matching lives in keywords.py, the work in
services/pipeline.py.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import EmailSettings, Tender
from app.services.credentials import get_app_password
from backend.config import get_logger

from .. import keywords as kw
from ..services import pipeline
from ..templating import templates

log = get_logger("agent_free.routes")

router = APIRouter(prefix="/agent-free", tags=["agent (no API)"])


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    tenders = (db.query(Tender)
                 .filter(Tender.source == pipeline.SOURCE)
                 .order_by(Tender.deadline_date.is_(None),
                           Tender.deadline_date.asc(),
                           Tender.id.desc())
                 .all())
    settings_row = db.query(EmailSettings).first()
    # The password is an environment variable (IMAP_APP_PASSWORD), not a
    # database column - see app.services.credentials. Checking the column
    # here made this banner claim the mailbox was unconfigured on a machine
    # where it was perfectly configured. Third copy of the same mistake;
    # pipeline.run_check and scheduler.start had it too.
    mailbox_ready = bool(settings_row and settings_row.imap_email
                         and get_app_password(settings_row))

    return templates.TemplateResponse("free_dashboard.html", {
        "request": request,
        "tenders": tenders,
        "keywords": kw.load(),
        "mailbox_ready": mailbox_ready,
        "settings": settings_row,
        "message": request.query_params.get("message"),
    })


@router.post("/check-now")
def check_now(db: Session = Depends(get_db)):
    """Run the mailbox check immediately rather than waiting for the timer."""
    counters = pipeline.run_check(db)
    message = counters.get("error") or pipeline.summary_message(counters)
    return RedirectResponse(f"/agent-free/?message={message}", status_code=303)


@router.get("/paste", response_class=HTMLResponse)
def paste_form(request: Request):
    return templates.TemplateResponse("free_paste.html", {"request": request})


@router.post("/paste")
def paste_digest(request: Request, digest: str = Form(""),
                 db: Session = Depends(get_db)):
    """
    Feed a digest in by hand.

    This exists so the agent can be proved to work before the mailbox is set
    up — it runs the exact same parsing, keywords and saving as the automatic
    check, so a result here means the automatic path will behave identically.
    """
    if not digest.strip():
        return RedirectResponse("/agent-free/paste", status_code=303)
    counters = pipeline.process_pasted_digest(db, digest)
    return RedirectResponse(
        f"/agent-free/?message={pipeline.summary_message(counters)}",
        status_code=303,
    )


@router.get("/keywords", response_class=HTMLResponse)
def keywords_form(request: Request):
    return templates.TemplateResponse("free_keywords.html", {
        "request": request,
        "keywords": kw.load(),
    })


@router.post("/keywords")
def save_keywords(english: str = Form(""), bengali: str = Form(""),
                  exclude: str = Form("")):
    def split(raw: str) -> list[str]:
        # One per line, or comma separated — accept whatever people type.
        parts: list[str] = []
        for line in raw.splitlines():
            parts.extend(p.strip() for p in line.split(","))
        return [p for p in parts if p]

    kw.save(kw.KeywordSet(english=split(english), bengali=split(bengali),
                          exclude=split(exclude)))
    log.info("keyword list updated")
    return RedirectResponse("/agent-free/?message=Keywords saved", status_code=303)


@router.post("/test-keywords", response_class=HTMLResponse)
def test_keywords(request: Request, sample: str = Form("")):
    """Try a tender title against the current list without saving anything."""
    result = kw.check(sample)
    return templates.TemplateResponse("free_keywords.html", {
        "request": request,
        "keywords": kw.load(),
        "sample": sample,
        "result": result,
    })
