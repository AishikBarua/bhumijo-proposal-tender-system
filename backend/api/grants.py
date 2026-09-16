"""Grant programme routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from ..database.audit_log import Actor, history
from ..models.grant import GrantCreate, GrantUpdate
from ..security.permissions import Principal, require
from ..services import grant_service
from .deps import current_actor, current_principal, require_delete_rights

router = APIRouter(prefix="/api/v1/grants", tags=["grants"])


@router.get("")
async def list_grants(
    status_filter: str | None = Query(default=None, alias="status"),
    result: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(current_principal),
) -> dict:
    require(principal, "grant.view")
    rows = grant_service.list_grants(
        status=status_filter, result=result, search=search, limit=limit, offset=offset
    )
    return {"count": len(rows), "grants": rows}


@router.get("/summary")
async def summary(principal: Principal = Depends(current_principal)) -> dict:
    require(principal, "grant.view")
    return grant_service.summary()


@router.get("/closing-soon")
async def closing_soon(
    within_days: int = Query(default=30, ge=1, le=365),
    principal: Principal = Depends(current_principal),
) -> dict:
    require(principal, "grant.view")
    return {"within_days": within_days, "grants": grant_service.closing_soon(within_days)}


@router.get("/{grant_id}")
async def get_grant(grant_id: str, principal: Principal = Depends(current_principal)) -> dict:
    require(principal, "grant.view")
    try:
        return grant_service.get(grant_id)
    except grant_service.NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{grant_id}/history")
async def get_history(grant_id: str, principal: Principal = Depends(current_principal)) -> dict:
    require(principal, "grant.view")
    return {"id": grant_id, "history": history("grant", grant_id)}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_grant(
    payload: GrantCreate,
    principal: Principal = Depends(current_principal),
    actor: Actor = Depends(current_actor),
) -> dict:
    require(principal, "grant.create")
    try:
        return grant_service.create(payload.model_dump(exclude_none=True), actor=actor)
    except grant_service.ValidationProblem as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/{grant_id}")
async def update_grant(
    grant_id: str,
    payload: GrantUpdate,
    principal: Principal = Depends(current_principal),
    actor: Actor = Depends(current_actor),
) -> dict:
    require(principal, "grant.edit")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="no fields to change")
    try:
        return grant_service.update(grant_id, changes, actor=actor)
    except grant_service.NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{grant_id}")
async def delete_grant(
    grant_id: str,
    request: Request,
    principal: Principal = Depends(current_principal),
    actor: Actor = Depends(current_actor),
) -> dict:
    require(principal, "grant.delete")
    require_delete_rights(request)
    try:
        return {"deleted": grant_service.delete(grant_id, actor=actor)}
    except grant_service.NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
