"""
A first draft mapping of the 47 free-text category values found in the live
data onto a short, reportable list.

This is a PROPOSAL, not a decision. Someone who knows the business should
review it — every original string is preserved in proposals.original_category
either way, so changing your mind later costs nothing.

The shortlist is derived from what the strings actually describe: the type of
document submitted, not the sector (the sector is already the entity).
"""

from __future__ import annotations

# The proposed shortlist, in the order it should appear in a dropdown.
SHORTLIST = [
    "EOI",                 # expression of interest
    "RFP",                 # request for proposal response
    "Proposal",            # a direct proposal
    "Tender",              # including e-GP tenders
    "Consultancy",
    "Meeting",             # initial meetings and pitches
    "Branding",
    "Adhoc",               # small one-off work
    "Other",               # anything that genuinely fits nowhere
]

# original string (exactly as it appears in the data) -> shortlist entry
MAPPING: dict[str, str] = {
    "": "Other",
    "Adhoc": "Adhoc",
    "Branding Proposal": "Branding",
    "Consultancy": "Consultancy",
    "Consultancy proposal": "Consultancy",
    "EOI": "EOI",
    "EOI (Online)": "EOI",
    "EOI -> RFP -> Presentation -> Got the Project": "EOI",
    "EOI -> RFP -> Presentation -> Rejected": "EOI",
    "EOI for": "EOI",
    "EOI for Park Public Space": "EOI",
    "EOI for Research": "EOI",
    "EOI for Toilet": "EOI",
    "EOI for Urban Planning & Development": "EOI",
    "EOI for building design": "EOI",
    "EOI for interior design": "EOI",
    "EOI for landscape design": "EOI",
    "EOI for park public space": "EOI",
    "Financial": "Other",
    "General": "Other",
    "Initial Meeting": "Meeting",
    "Initial meeting": "Meeting",
    "Meeting": "Meeting",
    "Proposal": "Proposal",
    "Proposal & Work": "Proposal",
    "Proposal (JV)": "Proposal",
    "Proposal for ETP": "Proposal",
    "Proposal for Grant": "Proposal",
    "Proposal for Urban Planning & Development": "Proposal",
    "Proposal for building design": "Proposal",
    "Proposal for consultancy": "Consultancy",
    "Proposal for interior": "Proposal",
    "RFP": "RFP",
    "RFP for  Interior Design": "RFP",
    "RFP for Design & Supervision": "RFP",
    "RFP for Research_Sanitation": "RFP",
    "RFP for Toilet": "RFP",
    "RFP for Urban Planning & Development": "RFP",
    "RFP for buiding design": "RFP",          # typo of the line below
    "RFP for building design": "RFP",
    "RFP for park public space": "RFP",
    "Tender": "Tender",
    "e-GP_EOI for Buidling Design": "EOI",
    "eGP": "Tender",
    "eGP (REOI) -> Re-tender": "Tender",
    "eGP (Tender ID: 1199337), EOI": "Tender",
    "eGp - Tender: 1151263": "Tender",
}


def map_category(original: str | None) -> tuple[str, bool]:
    """
    Returns (shortlist_name, was_confident).

    An unmapped value is not guessed at — it lands in "Other" and is reported
    so a person can decide where it really belongs.
    """
    key = (original or "").strip()
    if key in MAPPING:
        return MAPPING[key], True
    return "Other", False
