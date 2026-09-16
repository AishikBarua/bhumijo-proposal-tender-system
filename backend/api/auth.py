"""
Login routes. Scaffolded and working, but no accounts exist yet — the shared
token is still what the screens use, exactly as today.

When you are ready: create users, and the screens switch to /login.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from ..database.audit_log import Actor, record
from ..database.repositories import user_repo
from ..models.user import LoginRequest
from ..security import sessions
from ..security.passwords import verify_password
from ..security.permissions import Principal
from .deps import client_ip, current_principal

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login")
async def login(payload: LoginRequest, request: Request, response: Response) -> dict:
    # No SQL here on purpose: a route asks a question in business terms and
    # never knows how users and roles are stored.
    row = user_repo.get_by_username(payload.username)

    if not row or not row["is_active"] or not verify_password(payload.password, row["password_hash"]):
        # Same message either way — never reveal which half was wrong.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="that username and password do not match",
        )

    user_repo.record_login(row["id"])
    cookie = sessions.issue(row["id"], row["username"])
    response.set_cookie(
        sessions.COOKIE_NAME, cookie,
        httponly=True, samesite="lax", max_age=12 * 3600, path="/",
    )
    record(
        "login", "user", str(row["id"]),
        actor=Actor(user_id=row["id"], username=row["username"], client_ip=client_ip(request)),
        summary="signed in",
    )
    return {
        "ok": True,
        "user": {
            "id": row["id"],
            "username": row["username"],
            "display_name": row["display_name"],
            "role": row["role_code"],
        },
    }


@router.get("/session")
async def session(request: Request) -> dict:
    """
    Does this browser already know the token?

    The screens call this on load. If it says connected, nothing has to be
    typed — which is the whole point of the device cookie.
    """
    from .deps import device_is_known, is_trusted_network

    trusted = is_trusted_network(request)
    return {
        "connected": trusted or device_is_known(request),
        # So the screens can say WHY no token was needed, rather than
        # leaving people wondering whether anything is protecting this.
        "reason": "trusted network" if trusted else (
            "this device is remembered" if device_is_known(request) else "not connected"
        ),
    }


@router.post("/connect")
async def connect(payload: dict, request: Request, response: Response) -> dict:
    """
    Supply the shared token once. This browser is then remembered for 90 days
    in an HttpOnly cookie, so nobody has to type it again.
    """
    from ..security.tokens import token_ok

    supplied = (payload or {}).get("token", "")
    if not token_ok(supplied):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"ok": False, "error": "bad token"},
        )

    response.set_cookie(
        sessions.DEVICE_COOKIE_NAME,
        sessions.issue_device(),
        httponly=True,          # page scripts cannot read it
        samesite="lax",
        max_age=sessions.DEVICE_DAYS * 86400,
        path="/",
    )
    return {"ok": True, "remembered_for_days": sessions.DEVICE_DAYS}


@router.post("/forget")
async def forget(response: Response) -> dict:
    """Stop remembering this browser — it will need the token again."""
    response.delete_cookie(sessions.DEVICE_COOKIE_NAME, path="/")
    return {"ok": True}


@router.post("/logout")
async def logout(response: Response) -> dict:
    response.delete_cookie(sessions.COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
async def me(principal: Principal = Depends(current_principal)) -> dict:
    return {
        "user_id": principal.user_id,
        "username": principal.username,
        "role": principal.role_code,
        "permissions": sorted(principal.permissions),
        "entities": sorted(principal.entity_codes) if principal.entity_codes else "all",
        "using_shared_token": principal.role_code == "shared",
    }
