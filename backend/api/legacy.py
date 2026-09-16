"""
The nine endpoints today's screens already call, reproduced exactly.

This is what lets the rebuild go in without touching a single line of the
existing HTML. Every response has the same shape and the same keys as
proposal_server.py produced.

Two things behave better underneath, neither of them visible to the screens:
  * /proposals/save and /hitlist-data/save now insert-or-update instead of
    overwriting everything, so a stale browser cannot delete another
    person's work.
  * Every write is recorded in the audit log.

This whole file is deleted once the screens move to the /api/v1 endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import JSONResponse

from ..config import get_logger
from ..database.audit_log import Actor
from ..models import client as client_model
from ..models import grant as grant_model
from ..models import proposal as proposal_model
from ..security.tokens import token_ok
from ..services import client_service, grant_service, proposal_service
from .deps import current_actor, require_delete_rights, require_token

log = get_logger("api.legacy")

router = APIRouter(tags=["compatibility"])


# --- connection checks -------------------------------------------------

@router.get("/health")
async def health() -> dict:
    return {"ok": True}


@router.get("/verify")
async def verify(token: str = "") -> JSONResponse:
    if token_ok(token):
        return JSONResponse({"ok": True})
    return JSONResponse({"ok": False, "error": "bad token"}, status_code=401)


@router.get("/api/ping")
async def ping(request: Request) -> dict:
    supplied = request.headers.get("X-Auth-Token", "")
    authorised = token_ok(supplied)
    return {
        "ok": True,
        "authorized": authorised,
        "updatedAt": client_service.updated_at_millis() if authorised else 0,
    }


# --- proposals ---------------------------------------------------------

@router.get("/proposals/load")
async def load_proposals(_: str = Depends(require_token)) -> dict:
    rows = proposal_service.list_proposals()
    return {"ok": True, "proposals": [proposal_model.to_legacy_dict(r) for r in rows]}


@router.post("/proposals/save")
async def save_proposals(
    payload: dict = Body(default={}),
    _: str = Depends(require_token),
    actor: Actor = Depends(current_actor),
) -> JSONResponse:
    incoming = payload.get("proposals", [])
    if not isinstance(incoming, list):
        return JSONResponse(
            {"ok": False, "error": "proposals must be a list"}, status_code=400
        )

    result = proposal_service.save_many_legacy(incoming, actor=actor)
    log.info(
        "legacy save: %d created, %d updated, %d unchanged, %d skipped",
        result["created"], result["updated"], result["unchanged"], result["skipped"],
    )
    # blockedDeleted is kept in the response because the screens read it.
    # It is always 0 now: nothing is deleted by a save any more, so nothing
    # needs blocking.
    return JSONResponse({"ok": True, "blockedDeleted": 0, "saved": result})


@router.post("/proposals/delete")
async def delete_proposal(
    request: Request,
    payload: dict = Body(default={}),
    _: str = Depends(require_token),
    actor: Actor = Depends(current_actor),
) -> dict:
    require_delete_rights(request)
    deleted = False
    pid = payload.get("id")
    if pid:
        try:
            deleted = proposal_service.delete(pid, actor=actor)
        except proposal_service.NotFound:
            deleted = False
    return {"deleted": deleted}


# --- grant hitlist -----------------------------------------------------

@router.get("/hitlist-data/load")
async def load_hitlist(_: str = Depends(require_token)) -> dict:
    rows = grant_service.list_grants()
    return {"ok": True, "programs": [grant_model.to_legacy_dict(r) for r in rows]}


@router.post("/hitlist-data/save")
async def save_hitlist(
    payload: dict = Body(default={}),
    _: str = Depends(require_token),
    actor: Actor = Depends(current_actor),
) -> JSONResponse:
    incoming = payload.get("programs", [])
    if not isinstance(incoming, list):
        return JSONResponse(
            {"ok": False, "error": "programs must be a list"}, status_code=400
        )
    result = grant_service.save_many_legacy(incoming, actor=actor)
    log.info(
        "legacy hitlist save: %d created, %d updated, %d unchanged, %d skipped",
        result["created"], result["updated"], result["unchanged"], result["skipped"],
    )
    return JSONResponse({"ok": True, "blockedDeleted": 0, "saved": result})


@router.post("/hitlist-data/delete")
async def delete_hitlist(
    request: Request,
    payload: dict = Body(default={}),
    _: str = Depends(require_token),
    actor: Actor = Depends(current_actor),
) -> dict:
    require_delete_rights(request)
    deleted = False
    gid = payload.get("id")
    if gid is not None:
        try:
            deleted = grant_service.delete(str(gid), actor=actor)
        except grant_service.NotFound:
            deleted = False
    return {"deleted": deleted}


# --- clients -----------------------------------------------------------

@router.get("/api/clients")
async def get_clients(_: str = Depends(require_token)) -> dict:
    rows = client_service.list_clients()
    return {
        "ok": True,
        "clients": [client_model.to_legacy_dict(r) for r in rows],
        "updatedAt": client_service.updated_at_millis(),
    }


@router.post("/api/clients")
async def post_clients(
    payload: dict = Body(default={}),
    _: str = Depends(require_token),
    actor: Actor = Depends(current_actor),
) -> JSONResponse:
    incoming = payload.get("clients", [])
    if not isinstance(incoming, list):
        return JSONResponse(
            {"ok": False, "error": "clients must be a list"}, status_code=400
        )
    client_service.save_all_legacy(incoming, actor=actor)
    log.info("legacy clients save: %d record(s)", len(incoming))
    return JSONResponse({"ok": True, "updatedAt": client_service.updated_at_millis()})
