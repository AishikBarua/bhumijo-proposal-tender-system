from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PastContract, Certification
from app.services.company_profile import get_or_create_profile
from app.templating import templates

router = APIRouter()


@router.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request, db: Session = Depends(get_db)):
    profile = get_or_create_profile(db)
    contracts = db.query(PastContract).order_by(desc(PastContract.year)).all()
    certs = db.query(Certification).all()
    return templates.TemplateResponse("profile.html", {
        "request": request, "profile": profile, "contracts": contracts, "certs": certs
    })


@router.post("/profile/update")
def update_profile(
    sectors: str = Form(...),
    capabilities_summary: str = Form(...),
    geographic_reach: str = Form(...),
    db: Session = Depends(get_db),
):
    profile = get_or_create_profile(db)
    profile.sectors = sectors
    profile.capabilities_summary = capabilities_summary
    profile.geographic_reach = geographic_reach
    db.commit()
    return RedirectResponse(url="/agent/profile", status_code=303)


@router.post("/profile/contract/add")
def add_contract(
    client_name: str = Form(...),
    contract_value_bdt: str = Form(""),
    year: str = Form(""),
    scope_of_work: str = Form(...),
    location: str = Form(""),
    db: Session = Depends(get_db),
):
    contract = PastContract(
        client_name=client_name,
        contract_value_bdt=float(contract_value_bdt) if contract_value_bdt else None,
        year=int(year) if year else None,
        scope_of_work=scope_of_work,
        location=location or None,
    )
    db.add(contract)
    db.commit()
    return RedirectResponse(url="/agent/profile", status_code=303)


@router.post("/profile/contract/{contract_id}/delete")
def delete_contract(contract_id: int, db: Session = Depends(get_db)):
    db.query(PastContract).filter(PastContract.id == contract_id).delete()
    db.commit()
    return RedirectResponse(url="/agent/profile", status_code=303)


@router.post("/profile/cert/add")
def add_cert(
    name: str = Form(...),
    issuing_body: str = Form(""),
    valid_until: str = Form(""),
    db: Session = Depends(get_db),
):
    cert = Certification(name=name, issuing_body=issuing_body or None, valid_until=valid_until or None)
    db.add(cert)
    db.commit()
    return RedirectResponse(url="/agent/profile", status_code=303)


@router.post("/profile/cert/{cert_id}/delete")
def delete_cert(cert_id: int, db: Session = Depends(get_db)):
    db.query(Certification).filter(Certification.id == cert_id).delete()
    db.commit()
    return RedirectResponse(url="/agent/profile", status_code=303)
