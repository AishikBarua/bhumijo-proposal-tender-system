"""Grant programme queries — the hitlist, today a separate 1,048-line page."""

from __future__ import annotations

from typing import Any

from ...config import get_logger
from ..audit_log import Actor, SYSTEM, changed_fields, record
from ..connection import transaction
from .base import build_insert, build_update, fetch_all, fetch_one, scalar

log = get_logger("repo.grants")

TABLE = "grant_programmes"

COLUMNS = (
    "id", "name", "investor", "hq", "type", "cls", "focus", "ticket", "geo",
    "closing_date", "original_closing", "link", "file_loc",
    "status", "result", "comment",
    "created_at", "updated_at", "created_by", "updated_by",
)


def get(grant_id: str) -> dict | None:
    return fetch_one("SELECT * FROM grant_programmes WHERE id = ?", (str(grant_id),))


def list_all(
    *,
    status: str | None = None,
    result: str | None = None,
    search: str | None = None,
    closing_before: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[dict]:
    where: list[str] = []
    params: list[Any] = []

    if status:
        where.append("status = ?")
        params.append(status)
    if result:
        where.append("result = ?")
        params.append(result)
    if closing_before:
        where.append("closing_date IS NOT NULL AND closing_date <= ?")
        params.append(closing_before)
    if search:
        where.append("(name LIKE ? OR investor LIKE ? OR focus LIKE ? OR comment LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like, like, like])

    sql = "SELECT * FROM grant_programmes"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY closing_date IS NULL, closing_date ASC, id ASC"
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

    return fetch_all(sql, params)


def exists(grant_id: str) -> bool:
    return scalar("SELECT 1 FROM grant_programmes WHERE id = ?", (str(grant_id),)) is not None


def create(data: dict, *, actor: Actor = SYSTEM, conn=None) -> dict:
    payload = {k: v for k, v in data.items() if k in COLUMNS}
    payload["id"] = str(payload.get("id", ""))
    payload.setdefault("created_by", actor.user_id)
    payload["updated_by"] = actor.user_id

    if conn is None:
        with transaction() as conn:
            return _create(conn, payload, actor)
    return _create(conn, payload, actor)


def _create(conn, payload: dict, actor: Actor) -> dict:
    sql, params = build_insert(TABLE, payload)
    conn.execute(sql, params)
    record("create", "grant", payload["id"], actor=actor,
           summary=payload.get("name", ""), after=payload, conn=conn)
    return get(payload["id"]) or payload


def update(grant_id: str, data: dict, *, actor: Actor = SYSTEM, conn=None) -> dict | None:
    before = get(grant_id)
    if before is None:
        return None

    payload = {k: v for k, v in data.items() if k in COLUMNS and k != "id"}
    if not payload:
        return before
    payload["id"] = str(grant_id)
    payload["updated_at"] = scalar("SELECT datetime('now')")
    payload["updated_by"] = actor.user_id

    if conn is None:
        with transaction() as conn:
            return _update(conn, grant_id, payload, before, actor)
    return _update(conn, grant_id, payload, before, actor)


def _update(conn, grant_id: str, payload: dict, before: dict, actor: Actor) -> dict | None:
    sql, params = build_update(TABLE, payload, "id")
    conn.execute(sql, params)
    after = get(grant_id)
    fields = changed_fields(before, after)
    record("update", "grant", grant_id, actor=actor,
           summary="changed: " + ", ".join(fields) if fields else "no field changed",
           before=before, after=after, conn=conn)
    return after


def delete(grant_id: str, *, actor: Actor = SYSTEM) -> bool:
    before = get(grant_id)
    if before is None:
        return False
    with transaction() as conn:
        conn.execute("DELETE FROM grant_programmes WHERE id = ?", (str(grant_id),))
        record("delete", "grant", grant_id, actor=actor,
               summary=before.get("name", ""), before=before, conn=conn)
    return True


def upsert_many(items: list[dict], *, actor: Actor = SYSTEM) -> dict:
    """Insert-or-update, never delete-what-is-missing. See proposal_repo."""
    created = updated = unchanged = 0
    with transaction() as conn:
        for item in items:
            gid = str(item.get("id", ""))
            if not gid:
                continue
            if exists(gid):
                before = get(gid)
                comparable = {k: v for k, v in item.items() if k in COLUMNS}
                if all(before.get(k) == v for k, v in comparable.items()):
                    unchanged += 1
                    continue
                update(gid, item, actor=actor, conn=conn)
                updated += 1
            else:
                create(item, actor=actor, conn=conn)
                created += 1
    return {"created": created, "updated": updated, "unchanged": unchanged}
