"""Client rules."""

from __future__ import annotations

import time
from typing import Any

from ..database.audit_log import Actor, SYSTEM
from ..database.repositories import client_repo
from ..models import client as client_model
from .proposal_service import NotFound, ValidationProblem


def new_id() -> str:
    return f"c_{int(time.time() * 1000)}"


def get(client_id: str) -> dict:
    row = client_repo.get(client_id)
    if row is None:
        raise NotFound(f"no client with id {client_id}")
    return row


def list_clients(**filters) -> list[dict]:
    return client_repo.list_all(**filters)


def create(data: dict[str, Any], *, actor: Actor = SYSTEM) -> dict:
    payload = dict(data)
    payload.setdefault("id", new_id())
    if not (payload.get("name") or "").strip():
        raise ValidationProblem("a client needs a name")
    return client_repo.create(payload, actor=actor)


def update(client_id: str, changes: dict[str, Any], *, actor: Actor = SYSTEM) -> dict:
    get(client_id)
    updated = client_repo.update(client_id, changes, actor=actor)
    if updated is None:
        raise NotFound(f"no client with id {client_id}")
    return updated


def delete(client_id: str, *, actor: Actor = SYSTEM) -> bool:
    get(client_id)
    return client_repo.delete(client_id, actor=actor)


def save_all_legacy(items: list[dict], *, actor: Actor = SYSTEM) -> dict:
    rows = [client_model.from_legacy_dict(item) for item in items if item.get("id")]
    return client_repo.replace_all(rows, actor=actor)


def updated_at_millis() -> int:
    """The screens poll this to notice someone else's change."""
    rows = client_repo.list_all()
    if not rows:
        return 0
    latest = max((r.get("updated_at") or "") for r in rows)
    if not latest:
        return 0
    from datetime import datetime
    try:
        return int(datetime.fromisoformat(latest).timestamp() * 1000)
    except ValueError:
        return int(time.time() * 1000)
