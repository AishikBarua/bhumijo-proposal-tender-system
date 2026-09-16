"""Client routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from ..database.audit_log import Actor, history
from ..security.permissions import Principal, require
from ..services import client_service, proposal_service
from .deps import current_actor, current_principal, require_delete_rights

router = APIRouter(prefix="/api/v1/clients", tags=["clients"])


@router.get("")
async def list_clients(
    entity: str | None = Query(default=None),
    search: str | None = Query(default=None),
    principal: Principal = Depends(current_principal),
) -> dict:
    require(principal, "client.view")
    rows = client_service.list_clients(entity_code=entity, search=search)
    return {"count": len(rows), "clients": rows}


@router.get("/{client_id}")
async def get_client(client_id: str, principal: Principal = Depends(current_principal)) -> dict:
    require(principal, "client.view")
    try:
        return client_service.get(client_id)
    except client_service.NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{client_id}/history")
async def get_history(client_id: str, principal: Principal = Depends(current_principal)) -> dict:
    require(principal, "client.view")
    return {"id": client_id, "history": history("client", client_id)}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_client(
    payload: dict,
    principal: Principal = Depends(current_principal),
    actor: Actor = Depends(current_actor),
) -> dict:
    require(principal, "client.edit")
    try:
        return client_service.create(payload, actor=actor)
    except client_service.ValidationProblem as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/{client_id}")
async def update_client(
    client_id: str,
    payload: dict,
    principal: Principal = Depends(current_principal),
    actor: Actor = Depends(current_actor),
) -> dict:
    require(principal, "client.edit")
    try:
        return client_service.update(client_id, payload, actor=actor)
    except client_service.NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{client_id}")
async def delete_client(
    client_id: str,
    request: Request,
    principal: Principal = Depends(current_principal),
    actor: Actor = Depends(current_actor),
) -> dict:
    require(principal, "client.edit")
    require_delete_rights(request)
    try:
        return {"deleted": client_service.delete(client_id, actor=actor)}
    except client_service.NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/rebuild-from-won")
async def rebuild(
    principal: Principal = Depends(current_principal),
    actor: Actor = Depends(current_actor),
) -> dict:
    """The rule the browser used to run (buildClientsFromProposals)."""
    require(principal, "client.edit")
    return proposal_service.rebuild_clients_from_won(actor=actor)
