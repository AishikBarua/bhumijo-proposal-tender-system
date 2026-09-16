"""Shared request checks. Routes use these instead of repeating themselves."""

from __future__ import annotations

from ipaddress import ip_address, ip_network

from fastapi import Depends, HTTPException, Query, Request, status

from ..config import settings
from ..database.audit_log import Actor
from ..database.repositories import user_repo
from ..security import sessions
from ..security.permissions import Principal, SHARED_TOKEN_PRINCIPAL
from ..security.tokens import token_ok

LOCALHOST = {"127.0.0.1", "::1", "localhost"}


def client_ip(request: Request) -> str:
    if request.client is None:
        return ""
    return request.client.host or ""


def is_localhost(request: Request) -> bool:
    return client_ip(request) in LOCALHOST


def _supplied_token(request: Request, token: str | None) -> str | None:
    """The old screens send it two ways: ?token= and X-Auth-Token."""
    return token or request.headers.get("X-Auth-Token")


# Exactly the ranges a real office LAN uses, listed rather than inferred.
#
# Python's ip_address().is_private is broader than this — it also covers
# documentation and reserved ranges such as 203.0.113.x, which would have
# been trusted by mistake. Spelling the ranges out keeps the code and the
# documentation saying the same thing.
TRUSTED_NETWORKS = tuple(ip_network(n) for n in (
    "127.0.0.0/8",        # this PC
    "10.0.0.0/8",         # private
    "172.16.0.0/12",      # private
    "192.168.0.0/16",     # private — the office range
    "169.254.0.0/16",     # link-local
    "::1/128",            # this PC, IPv6
    "fc00::/7",           # private, IPv6
    "fe80::/10",          # link-local, IPv6
))


def is_trusted_network(request: Request) -> bool:
    """
    Is this request coming from the office's own network?

    Only the ranges above count. A request arriving from any public address
    is never trusted and still has to present the token.
    """
    if not settings.trust_local_network:
        return False

    host = client_ip(request)
    if not host:
        return False

    try:
        address = ip_address(host)
    except ValueError:
        return False

    return any(address in network for network in TRUSTED_NETWORKS
               if address.version == network.version)


def device_is_known(request: Request) -> bool:
    """Has this browser already proved it knows the shared token?"""
    return sessions.device_ok(request.cookies.get(sessions.DEVICE_COOKIE_NAME))


async def require_token(
    request: Request,
    token: str | None = Query(default=None),
) -> str:
    """
    A request is allowed if it carries the shared token OR comes from a
    browser that has already supplied it once and holds the device cookie.

    The cookie is what removes the retyping. It proves exactly what the token
    proves, and nothing more.
    """
    if is_trusted_network(request):
        return ""
    supplied = _supplied_token(request, token)
    if token_ok(supplied):
        return supplied or ""
    if device_is_known(request):
        return ""
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"ok": False, "error": "bad token"},
    )


async def current_principal(
    request: Request,
    token: str | None = Query(default=None),
) -> Principal:
    """
    A real session if one exists, otherwise the shared token.

    When accounts land, the token branch is deleted and this becomes the
    single door everyone comes through.
    """
    payload = sessions.read(request.cookies.get(sessions.COOKIE_NAME))
    if payload:
        row = user_repo.get_by_id(payload["uid"])
        if row:
            from ..security.permissions import for_role
            codes = user_repo.entity_codes_for(row["id"])
            principal = for_role(row["role_code"] or "viewer", codes or None)
            return Principal(
                user_id=row["id"],
                username=row["username"],
                role_code=principal.role_code,
                permissions=principal.permissions,
                entity_codes=principal.entity_codes,
                is_local=is_localhost(request),
            )

    supplied = _supplied_token(request, token)
    if (not is_trusted_network(request)
            and not token_ok(supplied)
            and not device_is_known(request)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"ok": False, "error": "bad token"},
        )
    return Principal(is_local=is_localhost(request))


async def current_actor(
    request: Request,
    principal: Principal = Depends(current_principal),
) -> Actor:
    return Actor(
        user_id=principal.user_id,
        username=principal.username,
        client_ip=client_ip(request),
    )


def require_delete_rights(request: Request) -> None:
    """
    Deleting was restricted to the server PC. That rule is kept until roles
    replace it, so behaviour does not change under anyone's feet — but it is
    now a setting rather than something buried in the code.
    """
    if settings.restrict_delete_to_localhost and not is_localhost(request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "ok": False,
                "error": "forbidden",
                "description": (
                    "Only the main PC (server) itself can delete a record. "
                    "Ask whoever is at the server PC to delete this one from there."
                ),
            },
        )
