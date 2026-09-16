"""
Proposal business rules. The API layer calls this; it never touches SQL, and
this never knows it is being called over HTTP.
"""

from __future__ import annotations

import time
from typing import Any

from ..config import get_logger
from ..database.audit_log import Actor, SYSTEM
from ..database.repositories import client_repo, proposal_repo, reference_repo
from ..models import proposal as proposal_model
from ..models.enums import DECIDED_RESULTS, ProposalResult, ProposalStatus

log = get_logger("services.proposals")


class ValidationProblem(Exception):
    """Something the user can fix — becomes a 400, not a 500."""


class NotFound(Exception):
    pass


def new_id() -> str:
    return f"p_{int(time.time() * 1000)}"


# --- reads ------------------------------------------------------------

def get(proposal_id: str) -> dict:
    row = proposal_repo.get(proposal_id)
    if row is None:
        raise NotFound(f"no proposal with id {proposal_id}")
    return row


def list_proposals(**filters) -> list[dict]:
    return proposal_repo.list_all(**filters)


# --- rules ------------------------------------------------------------

# Which status may follow which. Blank is allowed from anywhere because the
# existing data contains blanks and we do not invalidate history.
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "": {"Yet to be submitted", "Submitted", "Hold", "Drop", "Unable to submit", ""},
    "Yet to be submitted": {"Submitted", "Hold", "Drop", "Unable to submit", ""},
    "Submitted": {"Submitted", "Hold", "Drop", ""},
    "Hold": {"Yet to be submitted", "Submitted", "Drop", "Unable to submit", ""},
    "Drop": {"Yet to be submitted", "Hold", ""},
    "Unable to submit": {"Yet to be submitted", "Hold", ""},
}


def check_status_change(old_status: str, new_status: str) -> None:
    if old_status == new_status:
        return
    allowed = _ALLOWED_TRANSITIONS.get(old_status)
    if allowed is None:
        return
    if new_status not in allowed:
        raise ValidationProblem(
            f"cannot move a proposal from {old_status or 'blank'!r} "
            f"to {new_status or 'blank'!r}"
        )


def check_result_change(row: dict, new_result: str) -> None:
    """A result only makes sense once something has been submitted."""
    status = row.get("status", "")
    if new_result and status in ("Yet to be submitted", ""):
        raise ValidationProblem(
            f"cannot record a result of {new_result!r} while the status is "
            f"{status or 'blank'!r} — submit it first"
        )


def check_contract_required(row: dict, contract: str) -> None:
    """Accepted work should say whether a contract exists."""
    if row.get("result") == ProposalResult.ACCEPTED.value and not contract:
        log.info("proposal %s accepted with no contract flag set", row.get("id"))


# --- writes -----------------------------------------------------------

def create(data: dict[str, Any], *, actor: Actor = SYSTEM) -> dict:
    payload = dict(data)
    payload.setdefault("id", new_id())

    if proposal_repo.exists(payload["id"]):
        raise ValidationProblem(f"a proposal with id {payload['id']} already exists")

    payload = _resolve_category(payload)
    _validate(payload)
    return proposal_repo.create(payload, actor=actor)


def update(proposal_id: str, changes: dict[str, Any], *, actor: Actor = SYSTEM) -> dict:
    """Change one field or many — the thing the old full-replace could not do."""
    current = get(proposal_id)

    if "status" in changes and changes["status"] is not None:
        check_status_change(current.get("status", ""), changes["status"])
    if "result" in changes and changes["result"]:
        merged_status = changes.get("status") or current.get("status", "")
        check_result_change({**current, "status": merged_status}, changes["result"])

    payload = _resolve_category(dict(changes))
    _validate({**current, **payload}, partial=True)

    updated = proposal_repo.update(proposal_id, payload, actor=actor)
    if updated is None:
        raise NotFound(f"no proposal with id {proposal_id}")
    return updated


def delete(proposal_id: str, *, actor: Actor = SYSTEM) -> bool:
    get(proposal_id)  # raises NotFound
    return proposal_repo.delete(proposal_id, actor=actor)


def save_many_legacy(items: list[dict], *, actor: Actor = SYSTEM) -> dict:
    """
    The compatibility path for screens that still send the whole list.

    Rows missing from the payload are left alone rather than deleted, so a
    stale browser can no longer wipe another person's work.
    """
    rows = []
    skipped = []
    for item in items:
        try:
            row = proposal_model.from_legacy_dict(item)
            if not row.get("id"):
                skipped.append({"item": item, "why": "no id"})
                continue
            rows.append(_resolve_category(row))
        except Exception as exc:  # noqa: BLE001 — one bad row must not fail the batch
            skipped.append({"item": item, "why": str(exc)})

    result = proposal_repo.upsert_many(rows, actor=actor)
    result["skipped"] = len(skipped)
    if skipped:
        log.warning("legacy save skipped %d record(s): %s", len(skipped), skipped[:3])
    return result


# --- helpers ----------------------------------------------------------

def _resolve_category(payload: dict) -> dict:
    """Map a category name onto the category table, keeping the original."""
    name = payload.pop("category_name", None)
    if name is None:
        name = payload.get("original_category")
    if name:
        payload["original_category"] = name
        payload["category_id"] = reference_repo.ensure_category(name)
    return payload


def _validate(row: dict, *, partial: bool = False) -> None:
    if not partial and not (row.get("title") or "").strip():
        raise ValidationProblem("a proposal needs a title")

    model_input = {
        "title": row.get("title", "") or "",
        "entity_code": row.get("entity_code"),
        "client_name": row.get("client_name", "") or "",
        "status": row.get("status", "") or "",
        "result": row.get("result", "") or "",
        "contract": row.get("contract", "") or "",
        "open_date": row.get("open_date"),
        "close_date": row.get("close_date"),
        "start_date": row.get("start_date"),
        "end_date": row.get("end_date"),
    }
    try:
        proposal_model.ProposalBase(**model_input)
    except Exception as exc:  # pydantic ValidationError
        raise ValidationProblem(str(exc)) from exc


def rebuild_clients_from_won(*, actor: Actor = SYSTEM) -> dict:
    """
    The clients list is derived from accepted proposals — the browser used to
    do this (buildClientsFromProposals). Same rule, now on the server.
    """
    won = [r for r in proposal_repo.list_all() if r.get("result") in DECIDED_RESULTS
           and r.get("result") == ProposalResult.ACCEPTED.value]
    existing = {c["from_proposal_id"]: c for c in client_repo.list_all() if c.get("from_proposal_id")}

    created = 0
    for row in won:
        if row["id"] in existing:
            continue
        client_repo.create(
            {
                "id": f"c_{int(time.time() * 1000)}_{row['id']}",
                "name": row.get("client_name", ""),
                "entity_code": row.get("entity_code"),
                "project": row.get("title", ""),
                "value_amount": row.get("value_amount"),
                "value_currency": row.get("value_currency", "BDT"),
                "original_value": row.get("original_value", ""),
                "responsible": row.get("responsible", ""),
                "start_date": row.get("start_date"),
                "end_date": row.get("end_date"),
                "notes": row.get("remark", ""),
                "from_proposal_id": row["id"],
            },
            actor=actor,
        )
        created += 1

    return {"created": created, "from_won_proposals": len(won)}
