"""Grant programme rules — closing dates and stage tracking."""

from __future__ import annotations

import time
from datetime import date
from typing import Any

from ..config import get_logger
from ..database.audit_log import Actor, SYSTEM
from ..database.repositories import grant_repo
from ..models import grant as grant_model
from ..models.common import days_until
from .proposal_service import NotFound, ValidationProblem

log = get_logger("services.grants")


def new_id() -> str:
    return str(int(time.time() * 1000))


def get(grant_id: str) -> dict:
    row = grant_repo.get(grant_id)
    if row is None:
        raise NotFound(f"no grant programme with id {grant_id}")
    return row


def list_grants(**filters) -> list[dict]:
    return grant_repo.list_all(**filters)


def create(data: dict[str, Any], *, actor: Actor = SYSTEM) -> dict:
    payload = dict(data)
    payload.setdefault("id", new_id())
    if grant_repo.exists(payload["id"]):
        raise ValidationProblem(f"a grant programme with id {payload['id']} already exists")
    if not (payload.get("name") or "").strip():
        raise ValidationProblem("a grant programme needs a name")
    return grant_repo.create(payload, actor=actor)


def update(grant_id: str, changes: dict[str, Any], *, actor: Actor = SYSTEM) -> dict:
    get(grant_id)
    updated = grant_repo.update(grant_id, changes, actor=actor)
    if updated is None:
        raise NotFound(f"no grant programme with id {grant_id}")
    return updated


def delete(grant_id: str, *, actor: Actor = SYSTEM) -> bool:
    get(grant_id)
    return grant_repo.delete(grant_id, actor=actor)


def save_many_legacy(items: list[dict], *, actor: Actor = SYSTEM) -> dict:
    rows, skipped = [], []
    for item in items:
        try:
            row = grant_model.from_legacy_dict(item)
            if not row.get("id"):
                skipped.append({"item": item, "why": "no id"})
                continue
            rows.append(row)
        except Exception as exc:  # noqa: BLE001
            skipped.append({"item": item, "why": str(exc)})

    result = grant_repo.upsert_many(rows, actor=actor)
    result["skipped"] = len(skipped)
    if skipped:
        log.warning("legacy grant save skipped %d record(s)", len(skipped))
    return result


def closing_soon(within_days: int = 30, today: date | None = None) -> list[dict]:
    """Grant deadlines are the thing most worth an automatic reminder."""
    today = today or date.today()
    out = []
    for row in grant_repo.list_all():
        days = days_until(row.get("closing_date"), today)
        if days is None or days < 0 or days > within_days:
            continue
        out.append({
            "id": row["id"],
            "name": row.get("name", ""),
            "investor": row.get("investor", ""),
            "closing_date": row.get("closing_date"),
            "days_remaining": days,
            "status": row.get("status", ""),
            "link": row.get("link", ""),
        })
    return sorted(out, key=lambda r: r["days_remaining"])


def summary() -> dict[str, Any]:
    rows = grant_repo.list_all()
    with_dates = [r for r in rows if r.get("closing_date")]
    return {
        "total": len(rows),
        "with_closing_date": len(with_dates),
        "rolling": sum(1 for r in rows if (r.get("cls") or "").lower() == "rolling"),
        "closing_in_30_days": len(closing_soon(30)),
        "following_up": sum(1 for r in rows if (r.get("result") or "") == "Follow-up"),
    }
