"""Report routes — the figures, computed once, on the server."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..security.permissions import Principal, require
from ..services import metrics, reporting
from .deps import current_principal

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("/period")
async def period(
    start: str | None = Query(default=None, description="ISO date"),
    end: str | None = Query(default=None, description="ISO date"),
    entity: str | None = Query(default=None),
    principal: Principal = Depends(current_principal),
) -> dict:
    require(principal, "report.view")
    return reporting.period_report(start=start, end=end, entity_code=entity)


@router.get("/by-entity")
async def by_entity(
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    principal: Principal = Depends(current_principal),
) -> dict:
    require(principal, "report.view")
    return {"entities": metrics.by_entity(start=start, end=end)}


@router.get("/data-quality")
async def data_quality(principal: Principal = Depends(current_principal)) -> dict:
    """
    How much of the data can actually be reported on.

    Worth looking at before trusting any total: most proposals have no value
    recorded, so a pipeline figure is a floor, not the real number.
    """
    require(principal, "report.view")
    return metrics.data_quality()
