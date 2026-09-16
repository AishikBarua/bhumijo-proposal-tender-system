"""
Proposal routes — the reception desk. No SQL, no business rules, no HTML.

These are the endpoints the old system could not offer: fetch one record,
change one field, filter and page on the server.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse

from ..database.audit_log import Actor, history
from ..models.proposal import ProposalCreate, ProposalUpdate
from ..security.permissions import Principal, require, require_entity
from ..services import metrics, proposal_service, reporting
from .deps import current_actor, current_principal, require_delete_rights

router = APIRouter(prefix="/api/v1/proposals", tags=["proposals"])


def _not_found(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


def _bad_request(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("")
async def list_proposals(
    entity: str | None = Query(default=None, description="P&D, FM, WASH or Tech"),
    status_filter: str | None = Query(default=None, alias="status"),
    result: str | None = Query(default=None),
    search: str | None = Query(default=None, description="matches title, client or remark"),
    limit: int | None = Query(default=None, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(current_principal),
) -> dict:
    require(principal, "proposal.view")
    rows = proposal_service.list_proposals(
        entity_code=entity, status=status_filter, result=result,
        search=search, limit=limit, offset=offset,
    )
    if principal.entity_codes is not None:
        rows = [r for r in rows if r.get("entity_code") in principal.entity_codes]
    return {"count": len(rows), "proposals": rows}


@router.get("/summary")
async def summary(
    entity: str | None = Query(default=None),
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    principal: Principal = Depends(current_principal),
) -> dict:
    require(principal, "report.view")
    return metrics.summary(entity_code=entity, start=start, end=end)


@router.get("/deadlines")
async def deadlines(
    within_days: int = Query(default=30, ge=1, le=365),
    principal: Principal = Depends(current_principal),
) -> dict:
    require(principal, "proposal.view")
    return {
        "upcoming": metrics.upcoming_deadlines(within_days),
        "overdue": metrics.overdue(),
    }


@router.get("/export.csv", response_class=PlainTextResponse)
async def export_csv(
    entity: str | None = Query(default=None),
    principal: Principal = Depends(current_principal),
) -> PlainTextResponse:
    require(principal, "report.view")
    return PlainTextResponse(
        reporting.proposals_csv(entity_code=entity),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="proposals.csv"'},
    )


@router.get("/{proposal_id}")
async def get_proposal(
    proposal_id: str,
    principal: Principal = Depends(current_principal),
) -> dict:
    require(principal, "proposal.view")
    try:
        row = proposal_service.get(proposal_id)
    except proposal_service.NotFound as exc:
        raise _not_found(exc) from exc
    require_entity(principal, row.get("entity_code"))
    return row


@router.get("/{proposal_id}/history")
async def get_history(
    proposal_id: str,
    principal: Principal = Depends(current_principal),
) -> dict:
    """Who changed what, and when. There was no way to ask this before."""
    require(principal, "proposal.view")
    return {"id": proposal_id, "history": history("proposal", proposal_id)}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_proposal(
    payload: ProposalCreate,
    principal: Principal = Depends(current_principal),
    actor: Actor = Depends(current_actor),
) -> dict:
    require(principal, "proposal.create")
    require_entity(principal, payload.entity_code)
    try:
        return proposal_service.create(payload.model_dump(exclude_none=True), actor=actor)
    except proposal_service.ValidationProblem as exc:
        raise _bad_request(exc) from exc


@router.patch("/{proposal_id}")
async def update_proposal(
    proposal_id: str,
    payload: ProposalUpdate,
    principal: Principal = Depends(current_principal),
    actor: Actor = Depends(current_actor),
) -> dict:
    """
    Change one field without sending the other 178 records.

    This endpoint is the fix for the silent-overwrite problem.
    """
    require(principal, "proposal.edit")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise _bad_request(ValueError("no fields to change"))
    try:
        row = proposal_service.get(proposal_id)
        require_entity(principal, row.get("entity_code"))
        return proposal_service.update(proposal_id, changes, actor=actor)
    except proposal_service.NotFound as exc:
        raise _not_found(exc) from exc
    except proposal_service.ValidationProblem as exc:
        raise _bad_request(exc) from exc


@router.delete("/{proposal_id}")
async def delete_proposal(
    proposal_id: str,
    request: Request,
    principal: Principal = Depends(current_principal),
    actor: Actor = Depends(current_actor),
) -> dict:
    require(principal, "proposal.delete")
    require_delete_rights(request)
    try:
        row = proposal_service.get(proposal_id)
        require_entity(principal, row.get("entity_code"))
        return {"deleted": proposal_service.delete(proposal_id, actor=actor)}
    except proposal_service.NotFound as exc:
        raise _not_found(exc) from exc
