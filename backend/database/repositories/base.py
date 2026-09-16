"""Shared helpers for repositories. SQL lives in this package and nowhere else."""

from __future__ import annotations

from typing import Any, Iterable

from ..connection import get_connection


def rows_to_dicts(rows: Iterable) -> list[dict]:
    return [dict(row) for row in rows]


def build_insert(table: str, data: dict[str, Any]) -> tuple[str, list[Any]]:
    columns = list(data.keys())
    placeholders = ", ".join("?" for _ in columns)
    column_list = ", ".join(columns)
    sql = f"INSERT INTO {table} ({column_list}) VALUES ({placeholders})"
    return sql, [data[c] for c in columns]


def build_update(table: str, data: dict[str, Any], key_column: str) -> tuple[str, list[Any]]:
    columns = [c for c in data if c != key_column]
    assignments = ", ".join(f"{c} = ?" for c in columns)
    sql = f"UPDATE {table} SET {assignments} WHERE {key_column} = ?"
    return sql, [data[c] for c in columns] + [data[key_column]]


def fetch_one(sql: str, params: Iterable[Any] = ()) -> dict | None:
    row = get_connection().execute(sql, tuple(params)).fetchone()
    return dict(row) if row else None


def fetch_all(sql: str, params: Iterable[Any] = ()) -> list[dict]:
    return rows_to_dicts(get_connection().execute(sql, tuple(params)).fetchall())


def scalar(sql: str, params: Iterable[Any] = ()) -> Any:
    row = get_connection().execute(sql, tuple(params)).fetchone()
    return row[0] if row else None
