"""Syncs a tender to the separate "Bhumijo Proposal Tracker" app once it's marked
"selected" here (this app's closest equivalent to "Approved" - see app.models.Tender.status).

Called from app.routes.tenders.update_status, which wraps the call in try/except: a
sync failure (tracker down, bad token, network blip) must never block or fail the
approval itself, so everything that can fail lives in sync_tender() below and the
caller is responsible for catching and logging it.
"""
import logging

import httpx

from app.config import PROPOSAL_TRACKER_TOKEN, PROPOSAL_TRACKER_URL
from app.models import Tender

logger = logging.getLogger("tender_agent")

# Keyword -> entity bucket, checked in this order against title + scope_summary +
# organization (first match wins). Bhumijo's own sectors are WASH/sanitation and urban
# planning & design (see FULL_PROJECT_PROMPT.md's company_profile seed default) - WASH
# and P&D are checked first since they're the core business; Tech and FM are narrower
# categories a tender has to specifically mention. No tender-level sector field exists
# yet, so this is a best-effort guess, not an authoritative classification - the
# Proposal Tracker side can always be corrected by hand.
_ENTITY_KEYWORDS = [
    ("WASH", ("water", "sanitation", "sewer", "wash", "hygiene", "toilet", "latrine",
              "drainage", "faecal", "fecal", "septic")),
    ("Tech", ("software", "digital", "database", "application development", "ict",
              "gis", "information system", "smart toilet", "technology")),
    ("FM", ("facility management", "facilities management", "operation and maintenance",
            "o&m", "janitorial", "cleaning services", "security services", "housekeeping")),
    ("P&D", ("urban planning", "architecture", "master plan", "design consultancy",
             "spatial planning", "land use", "urban design")),
]
_DEFAULT_ENTITY = "P&D"  # Bhumijo's broadest/default sector when nothing else matches


def _infer_entity(tender: Tender) -> str:
    haystack = " ".join(filter(None, [tender.title, tender.scope_summary, tender.organization])).lower()
    for entity, keywords in _ENTITY_KEYWORDS:
        if any(kw in haystack for kw in keywords):
            return entity
    return _DEFAULT_ENTITY


def _build_remark(tender: Tender) -> str:
    """Reuses the Stage 4/5 fit-score reasoning as the summary, falling back to the
    scope summary, then to nothing - whichever exists first."""
    if tender.fit_reasons:
        return tender.fit_reasons
    if tender.scope_summary:
        return tender.scope_summary[:500]
    return ""


def _build_payload(tender: Tender) -> dict:
    return {
        "title": tender.title or "",
        "client": tender.organization or "",
        "category": tender.tender_type or "",  # already EOI/RFQ/RFP/Proposal/Enlistment/Other - see models.Tender.tender_type
        "entity": _infer_entity(tender),
        "openDate": tender.publish_date.isoformat() if tender.publish_date else None,
        "closeDate": tender.deadline_date.isoformat() if tender.deadline_date else None,
        "value": tender.estimated_value or None,
        "responsible": None,  # not tracked by this app - no assigned-staff field exists yet
        "remark": _build_remark(tender),
        "agentTenderId": tender.id,
    }


def sync_tender(tender: Tender) -> None:
    """POSTs `tender` to the Proposal Tracker. Raises on any failure (missing token,
    network error, non-2xx response) - callers must catch and log, never let this
    propagate into the status-update transaction."""
    if not PROPOSAL_TRACKER_TOKEN:
        raise RuntimeError("PROPOSAL_TRACKER_TOKEN is not set - cannot sync to Proposal Tracker")

    payload = _build_payload(tender)
    response = httpx.post(
        PROPOSAL_TRACKER_URL,
        json=payload,
        headers={"X-Auth-Token": PROPOSAL_TRACKER_TOKEN},
        timeout=10.0,
    )
    response.raise_for_status()
    logger.info("proposal tracker: synced tender %s (%r)", tender.id, tender.title)
