"""
Every user and role query in the system.

This exists because the login code was querying `users` and `roles` directly
from inside api/auth.py and api/deps.py — route files writing SQL, which is
exactly what the architecture forbids. A route should ask a question in
business terms ("who is this user?") and never know there is a table called
`users`, let alone how it joins to `roles`.

backend/tests/test_architecture.py fails the build if that creeps back.
"""

from __future__ import annotations

from ...config import get_logger
from ..audit_log import Actor, SYSTEM, record
from ..connection import transaction
from .base import fetch_all, fetch_one, scalar

log = get_logger("repo.users")

TABLE = "users"

# The shape every caller gets back. Kept in one place so a column rename
# happens here and nowhere else.
_SELECT = """
SELECT u.id, u.username, u.display_name, u.email, u.password_hash,
       u.is_active, u.created_at, u.last_login_at,
       r.code AS role_code, r.name AS role_name
FROM users u
LEFT JOIN roles r ON r.id = u.role_id
"""


def get_by_username(username: str) -> dict | None:
    """Used by login. Returns the password hash — only the login path should call this."""
    return fetch_one(_SELECT + " WHERE u.username = ?", (username,))


def get_by_id(user_id: int, *, active_only: bool = True) -> dict | None:
    sql = _SELECT + " WHERE u.id = ?"
    if active_only:
        sql += " AND u.is_active = 1"
    return fetch_one(sql, (user_id,))


def list_all() -> list[dict]:
    return fetch_all(_SELECT + " ORDER BY u.username COLLATE NOCASE")


def exists(username: str) -> bool:
    return scalar("SELECT 1 FROM users WHERE username = ?", (username,)) is not None


def entity_codes_for(user_id: int) -> list[str]:
    """
    Which entities this user may see.

    An empty list means every entity — there are no rows for a user with
    unrestricted access, which is what the permissions layer expects.
    """
    rows = fetch_all(
        "SELECT entity_code FROM user_entities WHERE user_id = ? ORDER BY entity_code",
        (user_id,),
    )
    return [r["entity_code"] for r in rows]


def role_id_for(role_code: str) -> int | None:
    return scalar("SELECT id FROM roles WHERE code = ?", (role_code,))


def create(
    *,
    username: str,
    display_name: str,
    password_hash: str,
    role_code: str,
    email: str | None = None,
    entity_codes: list[str] | None = None,
    actor: Actor = SYSTEM,
) -> dict | None:
    """Add an account. The caller hashes the password — this never sees a real one."""
    role_id = role_id_for(role_code)
    with transaction() as conn:
        cursor = conn.execute(
            """
            INSERT INTO users (username, display_name, email, password_hash, role_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (username, display_name, email, password_hash, role_id),
        )
        user_id = cursor.lastrowid

        for code in entity_codes or []:
            conn.execute(
                "INSERT INTO user_entities (user_id, entity_code) VALUES (?, ?)",
                (user_id, code),
            )

        record(
            "create", "user", str(user_id),
            actor=actor,
            summary=f"{username} ({role_code})",
            # Deliberately no password hash in the audit trail.
            after={"username": username, "display_name": display_name,
                   "role_code": role_code, "entity_codes": entity_codes or []},
            conn=conn,
        )
    return get_by_id(user_id)


def set_active(user_id: int, is_active: bool, *, actor: Actor = SYSTEM) -> bool:
    before = get_by_id(user_id, active_only=False)
    if before is None:
        return False
    with transaction() as conn:
        conn.execute("UPDATE users SET is_active = ? WHERE id = ?",
                     (1 if is_active else 0, user_id))
        record(
            "update", "user", str(user_id),
            actor=actor,
            summary=("enabled" if is_active else "disabled") + f" {before['username']}",
            before={"is_active": bool(before["is_active"])},
            after={"is_active": is_active},
            conn=conn,
        )
    return True


def record_login(user_id: int) -> None:
    with transaction() as conn:
        conn.execute(
            "UPDATE users SET last_login_at = datetime('now') WHERE id = ?", (user_id,)
        )


def count() -> int:
    return scalar("SELECT COUNT(*) FROM users") or 0
