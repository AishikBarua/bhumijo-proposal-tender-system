"""Every proposal query in the system. Nothing outside this file writes SQL."""

from __future__ import annotations

from typing import Any

from ...config import get_logger
from ..audit_log import Actor, SYSTEM, changed_fields, record
from ..connection import get_connection, transaction
from .base import build_insert, build_update, fetch_all, fetch_one, scalar

log = get_logger("repo.proposals")

TABLE = "proposals"

COLUMNS = (
    "id", "title", "entity_code", "category_id", "original_category",
    "client_name", "client_id", "value_amount", "value_currency", "original_value",
    "responsible", "open_date", "close_date", "start_date", "end_date",
    "original_open_date", "original_close_date", "original_start_date", "original_end_date",
    "status", "result", "contract", "remark", "original_created_at",
    "created_at", "updated_at", "created_by", "updated_by",
)

_SELECT = f"""
SELECT p.*, c.name AS category_name
FROM proposals p
LEFT JOIN categories c ON c.id = p.category_id
"""


def get(proposal_id: str) -> dict | None:
    return fetch_one(_SELECT + " WHERE p.id = ?", (proposal_id,))


def list_all(
    *,
    entity_code: str | None = None,
    status: str | None = None,
    result: str | None = None,
    search: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[dict]:
    """Filtering happens here, in the database — not by shipping all 179 rows."""
    where: list[str] = []
    params: list[Any] = []

    if entity_code:
        where.append("p.entity_code = ?")
        params.append(entity_code)
    if status:
        where.append("p.status = ?")
        params.append(status)
    if result:
        where.append("p.result = ?")
        params.append(result)
    if search:
        where.append("(p.title LIKE ? OR p.client_name LIKE ? OR p.remark LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like, like])

    sql = _SELECT
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY COALESCE(p.close_date, p.open_date) DESC, p.id DESC"
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

    return fetch_all(sql, params)


def count(**filters) -> int:
    return len(list_all(**filters))


def exists(proposal_id: str) -> bool:
    return scalar("SELECT 1 FROM proposals WHERE id = ?", (proposal_id,)) is not None


def create(data: dict, *, actor: Actor = SYSTEM, conn=None) -> dict:
    payload = {k: v for k, v in data.items() if k in COLUMNS}
    payload.setdefault("created_by", actor.user_id)
    payload["updated_by"] = actor.user_id

    own_transaction = conn is None
    if own_transaction:
        with transaction() as conn:
            return _create(conn, payload, actor)
    return _create(conn, payload, actor)


def _create(conn, payload: dict, actor: Actor) -> dict:
    sql, params = build_insert(TABLE, payload)
    conn.execute(sql, params)
    record(
        "create", "proposal", payload["id"],
        actor=actor, summary=payload.get("title", ""), after=payload, conn=conn,
    )
    return get(payload["id"]) or payload


def update(proposal_id: str, data: dict, *, actor: Actor = SYSTEM, conn=None) -> dict | None:
    before = get(proposal_id)
    if before is None:
        return None

    payload = {k: v for k, v in data.items() if k in COLUMNS and k != "id"}
    if not payload:
        return before
    payload["id"] = proposal_id
    payload["updated_at"] = _now()
    payload["updated_by"] = actor.user_id

    own_transaction = conn is None
    if own_transaction:
        with transaction() as conn:
            return _update(conn, proposal_id, payload, before, actor)
    return _update(conn, proposal_id, payload, before, actor)


def _update(conn, proposal_id: str, payload: dict, before: dict, actor: Actor) -> dict | None:
    sql, params = build_update(TABLE, payload, "id")
    conn.execute(sql, params)
    after = get(proposal_id)
    fields = changed_fields(before, after)
    record(
        "update", "proposal", proposal_id,
        actor=actor,
        summary="changed: " + ", ".join(fields) if fields else "no field changed",
        before=before, after=after, conn=conn,
    )
    return after


def delete(proposal_id: str, *, actor: Actor = SYSTEM) -> bool:
    before = get(proposal_id)
    if before is None:
        return False
    with transaction() as conn:
        conn.execute("DELETE FROM proposals WHERE id = ?", (proposal_id,))
        record(
            "delete", "proposal", proposal_id,
            actor=actor, summary=before.get("title", ""), before=before, conn=conn,
        )
    return True


def upsert_many(items: list[dict], *, actor: Actor = SYSTEM) -> dict:
    """
    Used by the compatibility endpoint that still sends the whole list.

    It updates what changed and inserts what is new. Crucially it does NOT
    delete rows that are missing from the payload — that is exactly the
    behaviour that used to make one person's work disappear.
    """
    created = updated = unchanged = 0
    with transaction() as conn:
        for item in items:
            pid = item.get("id")
            if not pid:
                continue
            if exists(pid):
                before = get(pid)
                comparable = {k: v for k, v in item.items() if k in COLUMNS}
                if all(before.get(k) == v for k, v in comparable.items()):
                    unchanged += 1
                    continue
                update(pid, item, actor=actor, conn=conn)
                updated += 1
            else:
                create(item, actor=actor, conn=conn)
                created += 1
    return {"created": created, "updated": updated, "unchanged": unchanged}


def distinct_values(column: str) -> list[str]:
    allowed = {"status", "result", "contract", "responsible", "client_name", "entity_code"}
    if column not in allowed:
        raise ValueError(f"not a filterable column: {column}")
    rows = fetch_all(
        f"SELECT DISTINCT {column} AS v FROM proposals WHERE {column} != '' ORDER BY v"
    )
    return [r["v"] for r in rows]


def _now() -> str:
    return scalar("SELECT datetime('now')")
