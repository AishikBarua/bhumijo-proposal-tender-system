"""Client shape and legacy translation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from .common import parse_date, parse_money, verbatim


class ClientBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    name: str = ""
    entity_code: str | None = None
    project: str = ""
    value_amount: float | None = None
    value_currency: str = "BDT"
    responsible: str = ""
    start_date: str | None = None
    end_date: str | None = None
    notes: str = ""
    from_proposal_id: str | None = None

    @field_validator("start_date", "end_date")
    @classmethod
    def _iso(cls, v: str | None) -> str | None:
        return parse_date(v) if v else None


class Client(ClientBase):
    id: str
    original_value: str = ""


def to_legacy_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id", ""),
        "name": row.get("name", "") or "",
        "entity": row.get("entity_code", "") or "",
        "project": row.get("project", "") or "",
        "value": row.get("original_value", "") or "",
        "responsible": row.get("responsible", "") or "",
        "startDate": row.get("start_date") or row.get("original_start_date", "") or "",
        "endDate": row.get("end_date") or row.get("original_end_date", "") or "",
        "notes": row.get("notes", "") or "",
        "fromProposalId": row.get("from_proposal_id", "") or "",
        **({"createdAt": row["original_created_at"]} if row.get("original_created_at") else {}),
    }


def from_legacy_dict(item: dict[str, Any]) -> dict[str, Any]:
    money = parse_money(item.get("value"))
    return {
        "id": item.get("id"),
        "name": verbatim(item.get("name")),
        "entity_code": item.get("entity") or None,
        "project": item.get("project", "") or "",
        "value_amount": money.amount,
        "value_currency": money.currency,
        "original_value": money.original,
        "responsible": verbatim(item.get("responsible")),
        "start_date": parse_date(item.get("startDate")),
        "end_date": parse_date(item.get("endDate")),
        "original_start_date": item.get("startDate", "") or "",
        "original_end_date": item.get("endDate", "") or "",
        "notes": item.get("notes", "") or "",
        "from_proposal_id": item.get("fromProposalId") or None,
        "original_created_at": str(item.get("createdAt", "") or ""),
    }
