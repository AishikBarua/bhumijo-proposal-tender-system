import logging

from fastapi import APIRouter, Request, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Tender
from app.services import proposal_tracker, tender_service
from app.templating import templates

router = APIRouter()
logger = logging.getLogger("tender_agent")

# The stepper (new -> tbd -> selected -> applied) plus the side/pipeline statuses -
# "rejected" is reachable from any stepper stage, "filtered_out"/"expired" are set by
# the app itself but a human can still correct a status via this same route.
_VALID_STATUSES = {"new", "tbd", "selected", "applied", "rejected", "filtered_out", "expired"}
_VALID_PURCHASE_STATUSES = {"not_purchased", "purchased", "na"}
_VALID_PRIORITIES = {"high", "medium", "low"}


@router.get("/tender/{tender_id}", response_class=HTMLResponse)
def tender_detail(tender_id: int, request: Request, db: Session = Depends(get_db)):
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    return templates.TemplateResponse("tender_detail.html", {"request": request, "t": tender})


@router.post("/tender/{tender_id}/status")
def update_status(tender_id: int, status: str = Form(...), db: Session = Depends(get_db)):
    if status not in _VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status!r}")
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if tender:
        became_selected = status == "selected" and tender.status != "selected"
        tender.status = status
        db.commit()
        # "selected" is this app's closest equivalent to "Approved" - sync to the
        # separate Bhumijo Proposal Tracker app. Never let a sync failure fail this
        # request: the approval itself must always succeed - see services.proposal_tracker.
        if became_selected:
            try:
                proposal_tracker.sync_tender(tender)
            except Exception as e:
                logger.error("proposal tracker sync failed for tender %s: %s", tender.id, e, exc_info=True)
    return RedirectResponse(url=f"/agent/tender/{tender_id}", status_code=303)


@router.post("/tender/{tender_id}/purchase-status")
def update_purchase_status(tender_id: int, purchase_status: str = Form(...), db: Session = Depends(get_db)):
    if purchase_status not in _VALID_PURCHASE_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid purchase_status: {purchase_status!r}")
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if tender:
        tender.purchase_status = purchase_status
        db.commit()
    return RedirectResponse(url=f"/agent/tender/{tender_id}", status_code=303)


@router.post("/tender/{tender_id}/priority")
def update_priority(tender_id: int, priority: str = Form(...), db: Session = Depends(get_db)):
    if priority not in _VALID_PRIORITIES:
        raise HTTPException(status_code=400, detail=f"Invalid priority: {priority!r}")
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if tender:
        tender.priority = priority
        db.commit()
    return RedirectResponse(url=f"/agent/tender/{tender_id}", status_code=303)


@router.post("/tender/{tender_id}/special-note")
def update_special_note(tender_id: int, special_note: str = Form(""), db: Session = Depends(get_db)):
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if tender:
        tender.special_note = special_note.strip() or None
        db.commit()
    return RedirectResponse(url=f"/agent/tender/{tender_id}", status_code=303)


# ---------- Tender ingestion (manual paste / PDF - Stage 5, human-triggered) ----------

@router.get("/add-tender", response_class=HTMLResponse)
def add_tender_form(request: Request):
    return templates.TemplateResponse("add_tender.html", {"request": request, "error": None})


@router.post("/add-tender")
async def add_tender(
    request: Request,
    tender_text: str = Form(""),
    source: str = Form("manual"),
    pdf_file: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    # Only the route can await the upload - handed to the service as raw bytes so the
    # actual extraction (extract_text_from_pdf) lives in services/tender_service.py,
    # not here.
    pdf_bytes = None
    if pdf_file is not None and pdf_file.filename:
        pdf_bytes = await pdf_file.read()

    try:
        tender = tender_service.process_manual_tender(db, tender_text, source, pdf_bytes=pdf_bytes)
    except Exception as e:
        return templates.TemplateResponse("add_tender.html", {
            "request": request, "error": f"AI processing failed: {e}"
        })

    if tender is None:
        return templates.TemplateResponse("add_tender.html", {
            "request": request, "error": "Please paste tender text or upload a PDF."
        })

    db.commit()
    return RedirectResponse(url=f"/agent/tender/{tender.id}", status_code=303)
