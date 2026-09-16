"""What a proposal must contain. Validation happens here, once, for everyone."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .common import parse_date, parse_money, verbatim
from .enums import ContractFlag, Entity, ProposalResult, ProposalStatus


class ProposalBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    title: str = ""
    entity_code: str | None = None
    category_name: str = ""
    client_name: str = ""
    client_id: str | None = None
    value_amount: float | None = None
    value_currency: str = "BDT"
    responsible: str = ""
    open_date: str | None = None
    close_date: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    status: str = ""
    result: str = ""
    contract: str = ""
    remark: str = ""

    @field_validator("entity_code")
    @classmethod
    def _known_entity(cls, v: str | None) -> str | None:
        if v in (None, ""):
            return None
        valid = {e.value for e in Entity}
        if v not in valid:
            raise ValueError(f"unknown entity {v!r}; expected one of {sorted(valid)}")
        return v

    @field_validator("status")
    @classmethod
    def _known_status(cls, v: str) -> str:
        valid = {s.value for s in ProposalStatus}
        if v not in valid:
            raise ValueError(f"unknown status {v!r}; expected one of {sorted(valid - {''})}")
        return v

    @field_validator("result")
    @classmethod
    def _known_result(cls, v: str) -> str:
        valid = {r.value for r in ProposalResult}
        if v not in valid:
            raise ValueError(f"unknown result {v!r}; expected one of {sorted(valid - {''})}")
        return v

    @field_validator("contract")
    @classmethod
    def _known_contract(cls, v: str) -> str:
        valid = {c.value for c in ContractFlag}
        if v not in valid:
            raise ValueError(f"contract must be Yes, No or blank, not {v!r}")
        return v

    @field_validator("open_date", "close_date", "start_date", "end_date")
    @classmethod
    def _iso_dates(cls, v: str | None) -> str | None:
        if not v:
            return None
        parsed = parse_date(v)
        if parsed is None:
            raise ValueError(f"date {v!r} is not a date I can read")
        return parsed

    @model_validator(mode="after")
    def _dates_make_sense(self) -> "ProposalBase":
        if self.open_date and self.close_date and self.close_date < self.open_date:
            raise ValueError("close date is before the open date")
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end date is before the start date")
        return self


class ProposalCreate(ProposalBase):
    id: str | None = None


class ProposalUpdate(BaseModel):
    """Every field optional — this is what makes changing one field possible."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    title: str | None = None
    entity_code: str | None = None
    category_name: str | None = None
    client_name: str | None = None
    client_id: str | None = None
    value_amount: float | None = None
    value_currency: str | None = None
    responsible: str | None = None
    open_date: str | None = None
    close_date: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    status: str | None = None
    result: str | None = None
    contract: str | None = None
    remark: str | None = None


class Proposal(ProposalBase):
    id: str
    original_value: str = ""
    original_category: str = ""
    created_at: str | None = None
    updated_at: str | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "Proposal":
        data = dict(row)
        data["category_name"] = data.get("category_name") or data.get("original_category") or ""
        return cls.model_construct(**{k: v for k, v in data.items() if k in cls.model_fields})


def to_legacy_dict(row: dict[str, Any]) -> dict[str, Any]:
    """
    The exact shape today's screens expect. The compatibility endpoints return
    this so the existing HTML keeps working with no change at all.
    """
    return {
        "id": row.get("id", ""),
        "title": row.get("title", "") or "",
        "entity": row.get("entity_code", "") or "",
        # The ORIGINAL string the user typed, not the mapped shortlist value.
        # Reporting groups by category_name; the screens still show what was typed,
        # so nothing a person sees changes.
        "category": row.get("original_category", "") or "",
        "client": row.get("client_name", "") or "",
        "value": row.get("original_value", "") or "",
        "responsible": row.get("responsible", "") or "",
        "openDate": row.get("open_date") or row.get("original_open_date", "") or "",
        "closeDate": row.get("close_date") or row.get("original_close_date", "") or "",
        "status": row.get("status", "") or "",
        "result": row.get("result", "") or "",
        "contract": row.get("contract", "") or "",
        "startDate": row.get("start_date") or row.get("original_start_date", "") or "",
        "endDate": row.get("end_date") or row.get("original_end_date", "") or "",
        "remark": row.get("remark", "") or "",
        # Only records that actually had a createdAt get one back. 156 of the
        # 179 never had this field and must not acquire one.
        **({"createdAt": row["original_created_at"]} if row.get("original_created_at") else {}),
    }


def from_legacy_dict(item: dict[str, Any]) -> dict[str, Any]:
    """Turn what the current screens send into database columns."""
    money = parse_money(item.get("value"))
    return {
        "id": item.get("id"),
        "title": verbatim(item.get("title")),
        "entity_code": item.get("entity") or None,
        "original_category": verbatim(item.get("category")),
        "client_name": verbatim(item.get("client")),
        "value_amount": money.amount,
        "value_currency": money.currency,
        "original_value": money.original,
        "responsible": verbatim(item.get("responsible")),
        "open_date": parse_date(item.get("openDate")),
        "close_date": parse_date(item.get("closeDate")),
        "start_date": parse_date(item.get("startDate")),
        "end_date": parse_date(item.get("endDate")),
        "original_open_date": item.get("openDate", "") or "",
        "original_close_date": item.get("closeDate", "") or "",
        "original_start_date": item.get("startDate", "") or "",
        "original_end_date": item.get("endDate", "") or "",
        "status": item.get("status", "") or "",
        "result": item.get("result", "") or "",
        "contract": item.get("contract", "") or "",
        "remark": verbatim(item.get("remark")),
    }
