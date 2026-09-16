"""Entities, categories and other reference lists."""

from __future__ import annotations

from ..connection import transaction
from .base import fetch_all, fetch_one, scalar


def entities() -> list[dict]:
    return fetch_all("SELECT * FROM entities WHERE is_active = 1 ORDER BY sort_order")


def entity_codes() -> list[str]:
    return [e["code"] for e in entities()]


def entity_by_code(code: str) -> dict | None:
    return fetch_one("SELECT * FROM entities WHERE code = ?", (code,))


def categories() -> list[dict]:
    return fetch_all("SELECT * FROM categories WHERE is_active = 1 ORDER BY sort_order, name")


def category_id_for(name: str) -> int | None:
    if not name:
        return None
    return scalar("SELECT id FROM categories WHERE name = ?", (name,))


def ensure_category(name: str, sort_order: int = 500) -> int | None:
    """Add a category if it is genuinely new. Used by the migration."""
    if not name:
        return None
    existing = category_id_for(name)
    if existing:
        return existing
    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO categories (name, sort_order) VALUES (?, ?)", (name, sort_order)
        )
        return cur.lastrowid


def roles() -> list[dict]:
    return fetch_all("SELECT * FROM roles ORDER BY id")


def permissions_for_role(role_code: str) -> list[str]:
    rows = fetch_all(
        """
        SELECT p.code FROM permissions p
        JOIN role_permissions rp ON rp.permission_id = p.id
        JOIN roles r ON r.id = rp.role_id
        WHERE r.code = ? ORDER BY p.code
        """,
        (role_code,),
    )
    return [r["code"] for r in rows]
