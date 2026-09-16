"""
Who may do what, and to which entity.

Scaffolded now against the role grid in the database. Until accounts exist,
allow_all() is what the shared token gets — the same access everyone has
today, no more.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..database.repositories import reference_repo


@dataclass(frozen=True)
class Principal:
    """Whoever is making the request."""

    user_id: int | None = None
    username: str = "shared-token"
    role_code: str = "shared"
    permissions: frozenset[str] = field(default_factory=frozenset)
    entity_codes: frozenset[str] | None = None   # None means every entity
    is_local: bool = False

    def can(self, permission: str) -> bool:
        if self.role_code == "shared":
            return True          # today's behaviour, unchanged
        return permission in self.permissions

    def may_touch_entity(self, entity_code: str | None) -> bool:
        if self.entity_codes is None:
            return True
        if entity_code is None:
            return True
        return entity_code in self.entity_codes


SHARED_TOKEN_PRINCIPAL = Principal()


def for_role(role_code: str, entity_codes: list[str] | None = None) -> Principal:
    return Principal(
        role_code=role_code,
        permissions=frozenset(reference_repo.permissions_for_role(role_code)),
        entity_codes=frozenset(entity_codes) if entity_codes else None,
    )


class Forbidden(Exception):
    """Becomes a 403."""


def require(principal: Principal, permission: str) -> None:
    if not principal.can(permission):
        raise Forbidden(f"you do not have permission to {permission}")


def require_entity(principal: Principal, entity_code: str | None) -> None:
    if not principal.may_touch_entity(entity_code):
        raise Forbidden(f"you do not have access to the {entity_code} entity")
