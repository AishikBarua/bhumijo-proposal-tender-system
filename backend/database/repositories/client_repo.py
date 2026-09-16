"""Client queries."""

from __future__ import annotations

from ...config import get_logger
from ..audit_log import Actor, SYSTEM, changed_fields, record
from ..connection import transaction
from .base import build_insert, build_update, fetch_all, fetch_one, scalar

log = get_logger("repo.clients")

TABLE = "clients"

COLUMNS = (
    "id", "name", "entity_code", "project", "value_amount", "value_currency",
    "original_value", "responsible", "start_date", "end_date",
    "original_start_date", "original_end_date", "notes", "from_proposal_id",
    "original_created_at",
    "created_at", "updated_at",
)


def get(client_id: str) -> dict | None:
    return fetch_one("SELECT * FROM clients WHERE id = ?", (client_id,))


def list_all(*, entity_code: str | None = None, search: str | None = None) -> list[dict]:
    where, params = [], []
    if entity_code:
        where.append("entity_code = ?")
        params.append(entity_code)
    if search:
        where.append("(name LIKE ? OR project LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    sql = "SELECT * FROM clients"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY name COLLATE NOCASE"
    return fetch_all(sql, params)


def exists(client_id: str) -> bool:
    return scalar("SELECT 1 FROM clients WHERE id = ?", (client_id,)) is not None


def create(data: dict, *, actor: Actor = SYSTEM, conn=None) -> dict:
    payload = {k: v for k, v in data.items() if k in COLUMNS}
    if conn is None:
        with transaction() as conn:
            return _create(conn, payload, actor)
    return _create(conn, payload, actor)


def _create(conn, payload: dict, actor: Actor) -> dict:
    sql, params = build_insert(TABLE, payload)
    conn.execute(sql, params)
    record("create", "client", payload["id"], actor=actor,
           summary=payload.get("name", ""), after=payload, conn=conn)
    return get(payload["id"]) or payload


def update(client_id: str, data: dict, *, actor: Actor = SYSTEM, conn=None) -> dict | None:
    before = get(client_id)
    if before is None:
        return None
    payload = {k: v for k, v in data.items() if k in COLUMNS and k != "id"}
    if not payload:
        return before
    payload["id"] = client_id
    payload["updated_at"] = scalar("SELECT datetime('now')")

    if conn is None:
        with transaction() as conn:
            return _update(conn, client_id, payload, before, actor)
    return _update(conn, client_id, payload, before, actor)


def _update(conn, client_id: str, payload: dict, before: dict, actor: Actor) -> dict | None:
    sql, params = build_update(TABLE, payload, "id")
    conn.execute(sql, params)
    after = get(client_id)
    fields = changed_fields(before, after)
    record("update", "client", client_id, actor=actor,
           summary="changed: " + ", ".join(fields) if fields else "no field changed",
           before=before, after=after, conn=conn)
    return after


def delete(client_id: str, *, actor: Actor = SYSTEM) -> bool:
    before = get(client_id)
    if before is None:
        return False
    with transaction() as conn:
        conn.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        record("delete", "client", client_id, actor=actor,
               summary=before.get("name", ""), before=before, conn=conn)
    return True


def replace_all(items: list[dict], *, actor: Actor = SYSTEM) -> dict:
    """
    The clients screen genuinely does own the whole list (it is rebuilt from
    won proposals), so a full replace is correct here — but it is done in one
    transaction and the previous list is written to the audit log first.
    """
    before = list_all()
    created = updated = 0
    incoming_ids = {c.get("id") for c in items if c.get("id")}

    with transaction() as conn:
        record("update", "client_list", "all", actor=actor,
               summary=f"{len(before)} -> {len(items)} clients",
               before=before, after=items, conn=conn)
        for item in items:
            cid = item.get("id")
            if not cid:
                continue
            if exists(cid):
                update(cid, item, actor=actor, conn=conn)
                updated += 1
            else:
                create(item, actor=actor, conn=conn)
                created += 1
        for row in before:
            if row["id"] not in incoming_ids:
                conn.execute("DELETE FROM clients WHERE id = ?", (row["id"],))

    removed = len([r for r in before if r["id"] not in incoming_ids])
    return {"created": created, "updated": updated, "removed": removed}
