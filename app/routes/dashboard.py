from datetime import date

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Tender
from app.templating import templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    show_filtered: bool = False,
    show_expired: bool = False,
    q: str = "",
    db: Session = Depends(get_db),
):
    query = db.query(Tender)
    if not show_filtered:
        query = query.filter(Tender.status != "filtered_out")
    if not show_expired:
        query = query.filter(Tender.status != "expired")

    q = (q or "").strip()
    if q:
        like = f"%{q}%"
        query = query.filter(or_(
            Tender.title.ilike(like),
            Tender.organization.ilike(like),
            Tender.district.ilike(like),
            Tender.tender_ref.ilike(like),
        ))

    tenders = query.order_by(desc(Tender.processed_at)).all()

    shortlisted = [t for t in tenders if t.hard_filter_pass is True and (t.fit_score or 0) >= 50]
    needs_review = sorted(
        (t for t in tenders if t.hard_filter_pass is None and t.status not in ("filtered_out", "expired")),
        key=lambda t: (t.deadline_date is None, t.deadline_date or date.max),
    )
    filtered_out = [t for t in tenders if t.status == "filtered_out"]
    expired = [t for t in tenders if t.status == "expired"]
    others = [t for t in tenders
              if t not in shortlisted and t not in needs_review and t not in filtered_out and t not in expired]

    filtered_out_count = db.query(Tender).filter(Tender.status == "filtered_out").count()
    expired_count = db.query(Tender).filter(Tender.status == "expired").count()
    urgent_count = len([
        t for t in tenders
        if t.days_remaining is not None and t.days_remaining <= 7
        and t.status in ("new", "tbd", "selected")
    ])

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "shortlisted": shortlisted,
        "needs_review": needs_review,
        "others": others,
        "filtered_out": filtered_out,
        "filtered_out_count": filtered_out_count,
        "expired": expired,
        "expired_count": expired_count,
        "urgent_count": urgent_count,
        "show_filtered": show_filtered,
        "show_expired": show_expired,
        "q": q,
        "total": len(tenders),
    })
