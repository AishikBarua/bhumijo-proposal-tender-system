"""Entities, categories and other lists the screens need to build dropdowns."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..database.repositories import proposal_repo, reference_repo
from ..security.permissions import Principal
from .deps import current_principal

router = APIRouter(prefix="/api/v1/reference", tags=["reference"])


@router.get("/entities")
async def entities(_: Principal = Depends(current_principal)) -> dict:
    return {"entities": reference_repo.entities()}


@router.get("/categories")
async def categories(_: Principal = Depends(current_principal)) -> dict:
    return {"categories": reference_repo.categories()}


@router.get("/responsible")
async def responsible(_: Principal = Depends(current_principal)) -> dict:
    """The names already in use — the old custom-name list, from real data."""
    return {"names": proposal_repo.distinct_values("responsible")}


@router.get("/statuses")
async def statuses(_: Principal = Depends(current_principal)) -> dict:
    return {
        "statuses": proposal_repo.distinct_values("status"),
        "results": proposal_repo.distinct_values("result"),
    }
