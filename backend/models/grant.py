"""Grant programme shape and the translation to/from what the hitlist sends."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from .common import parse_date, verbatim


class GrantBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    name: str = ""
    investor: str = ""
    hq: str = ""
    type: str = ""
    cls: str = ""
    focus: str = ""
    ticket: str = ""
    geo: str = ""
    closing_date: str | None = None
    link: str = ""
    file_loc: str = ""
    status: str = ""
    result: str = ""
    comment: str = ""

    @field_validator("closing_date")
    @classmethod
    def _iso(cls, v: str | None) -> str | None:
        if not v:
            return None
        parsed = parse_date(v)
        if parsed is None:
            raise ValueError(f"closing date {v!r} is not a date I can read")
        return parsed


class GrantCreate(GrantBase):
    id: str | None = None


class GrantUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    name: str | None = None
    investor: str | None = None
    hq: str | None = None
    type: str | None = None
    cls: str | None = None
    focus: str | None = None
    ticket: str | None = None
    geo: str | None = None
    closing_date: str | None = None
    link: str | None = None
    file_loc: str | None = None
    status: str | None = None
    result: str | None = None
    comment: str | None = None


class Grant(GrantBase):
    id: str
    original_closing: str | None = None


def to_legacy_dict(row: dict[str, Any]) -> dict[str, Any]:
    """Exactly the keys the hitlist page reads today."""
    raw_id = row.get("id", "")
    try:
        legacy_id: Any = int(raw_id)
    except (TypeError, ValueError):
        legacy_id = raw_id
    out = {
        "id": legacy_id,
        "name": row.get("name", "") or "",
        "investor": row.get("investor", "") or "",
        "hq": row.get("hq", "") or "",
        "type": row.get("type", "") or "",
        "cls": row.get("cls", "") or "",
        "focus": row.get("focus", "") or "",
        "ticket": row.get("ticket", "") or "",
        "geo": row.get("geo", "") or "",
        # Absent stays absent: a record with no closing date must not come
        # back with an empty string where the file held null.
        "closing": row.get("closing_date") or row.get("original_closing"),
        "link": row.get("link", "") or "",
        "status": row.get("status", "") or "",
        "result": row.get("result", "") or "",
        "comment": row.get("comment", "") or "",
    }
    # fileLoc was present on only 15 of 192 records; keep that faithful.
    if row.get("file_loc"):
        out["fileLoc"] = row["file_loc"]
    return out


def from_legacy_dict(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(item.get("id", "")),
        "name": verbatim(item.get("name")),
        "investor": verbatim(item.get("investor")),
        "hq": verbatim(item.get("hq")),
        "type": verbatim(item.get("type")),
        "cls": verbatim(item.get("cls")),
        "focus": item.get("focus", "") or "",
        "ticket": item.get("ticket", "") or "",
        "geo": verbatim(item.get("geo")),
        "closing_date": parse_date(item.get("closing")),
        "original_closing": item.get("closing"),
        "link": item.get("link", "") or "",
        "file_loc": item.get("fileLoc", "") or "",
        "status": item.get("status", "") or "",
        "result": item.get("result", "") or "",
        "comment": item.get("comment", "") or "",
    }
