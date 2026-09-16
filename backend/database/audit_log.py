"""
Who changed what, when, and what it looked like before.

Nothing in the old system recorded this, so "who marked this Rejected?" had
no answer. Every write path calls record() — it is not optional.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ..config import get_logger
from .connection import get_connection

log = get_logger("database.audit")


@dataclass(frozen=True)
class Actor:
    """Who is making a change. Until logins land, this is the shared token."""

    user_id: int | None = None
    username: str = "shared-token"
    client_ip: str = ""


SYSTEM = Actor(username="system")


def _dump(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return json.dumps({"unserialisable": str(value)})


def record(
    action: str,
    record_type: str,
    record_id: str = "",
    *,
    actor: Actor = SYSTEM,
    summary: str = "",
    before: Any = None,
    after: Any = None,
    conn=None,
) -> None:
    conn = conn or get_connection()
    conn.execute(
        """
        INSERT INTO audit_log
            (user_id, username, action, record_type, record_id,
             summary, before_json, after_json, client_ip)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            actor.user_id,
            actor.username,
            action,
            record_type,
            str(record_id),
            summary,
            _dump(before),
            _dump(after),
            actor.client_ip,
        ),
    )


def changed_fields(before: dict | None, after: dict | None) -> list[str]:
    """Which fields actually differ — keeps audit summaries readable."""
    if not before or not after:
        return []
    return sorted(
        key
        for key in set(before) | set(after)
        if before.get(key) != after.get(key) and not key.startswith("original_")
        and key not in ("updated_at", "created_at")
    )


def history(record_type: str, record_id: str, limit: int = 100) -> list[dict]:
    rows = get_connection().execute(
        """
        SELECT id, occurred_at, username, action, summary, before_json, after_json
        FROM audit_log
        WHERE record_type = ? AND record_id = ?
        ORDER BY id DESC LIMIT ?
        """,
        (record_type, str(record_id), limit),
    ).fetchall()
    return [dict(row) for row in rows]


def recent(limit: int = 200) -> list[dict]:
    rows = get_connection().execute(
        """
        SELECT id, occurred_at, username, action, record_type, record_id, summary
        FROM audit_log ORDER BY id DESC LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]
