"""The audit trail, readable. Nothing in the old system could answer these."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..database.audit_log import history, recent
from ..security.permissions import Principal, require
from .deps import current_principal

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get("")
async def list_recent(
    limit: int = Query(default=100, ge=1, le=1000),
    principal: Principal = Depends(current_principal),
) -> dict:
    require(principal, "audit.view")
    return {"entries": recent(limit)}


@router.get("/{record_type}/{record_id}")
async def for_record(
    record_type: str,
    record_id: str,
    principal: Principal = Depends(current_principal),
) -> dict:
    require(principal, "audit.view")
    return {
        "record_type": record_type,
        "record_id": record_id,
        "history": history(record_type, record_id),
    }
