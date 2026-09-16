"""Shared company profile helpers - used by both app.main (profile page) and
app.pipeline (every AI evaluation call needs this as reference data)."""
from sqlalchemy.orm import Session

from app.models import CompanyProfile, PastContract, Certification


def get_or_create_profile(db: Session) -> CompanyProfile:
    profile = db.query(CompanyProfile).first()
    if not profile:
        profile = CompanyProfile(
            company_name="Bhumijo",
            sectors="WASH/sanitation infrastructure, urban planning & design consultancy",
            capabilities_summary="Design, construction, renovation, and operation of public "
                                  "toilets and sanitation facilities; smart toilet technology; "
                                  "vehicle/mobile toilet rental; sanitation product supply; "
                                  "architecture, urban planning, and urban design consultancy.",
            geographic_reach="Nationwide, based in Dhaka",
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


_RELEVANCE_SUMMARY_WORD_CAP = 100


def build_relevance_summary(company_profile: dict) -> str:
    """Short profile summary for Stage 3 (is_relevant_listing), which runs ~1,000
    times/month - the full profile_to_dict() payload belongs in Stage 4/5 (~200/month),
    not here, so this is deliberately capped to keep the high-volume call cheap.
    Returns "" if the profile has nothing usable yet, letting the caller fall back to
    the hardcoded sector text in app.ai.is_relevant_listing."""
    if not company_profile:
        return ""

    parts = []
    sectors = (company_profile.get("sectors") or "").strip()
    if sectors:
        parts.append(f"Sectors: {sectors}.")
    capabilities = (company_profile.get("capabilities_summary") or "").strip()
    if capabilities:
        parts.append(f"Capabilities: {capabilities}")

    values = [c["value_bdt"] for c in (company_profile.get("past_contracts") or []) if c.get("value_bdt")]
    if values:
        parts.append(f"Past contract values range roughly {min(values):,.0f}-{max(values):,.0f} BDT.")

    summary = " ".join(parts)
    words = summary.split()
    if len(words) > _RELEVANCE_SUMMARY_WORD_CAP:
        summary = " ".join(words[:_RELEVANCE_SUMMARY_WORD_CAP]) + "..."
    return summary


def profile_to_dict(db: Session) -> dict:
    profile = get_or_create_profile(db)
    contracts = db.query(PastContract).all()
    certs = db.query(Certification).all()
    return {
        "company_name": profile.company_name,
        "sectors": profile.sectors,
        "capabilities_summary": profile.capabilities_summary,
        "geographic_reach": profile.geographic_reach,
        "past_contracts": [
            {
                "client": c.client_name,
                "value_bdt": c.contract_value_bdt,
                "year": c.year,
                "scope": c.scope_of_work,
                "location": c.location,
            }
            for c in contracts
        ],
        "certifications": [
            {"name": c.name, "issuing_body": c.issuing_body, "valid_until": c.valid_until}
            for c in certs
        ],
    }
