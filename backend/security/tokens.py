"""
The shared access token, kept only so today's screens keep working.

Two changes from the old behaviour, both of which close real holes:
  * The token file is never served over HTTP (see api/static.py — there is
    no catch-all static handler any more).
  * Comparison is constant time, as it already was.

This whole module disappears when named accounts land.
"""

from __future__ import annotations

import hmac
import secrets

from ..config import get_logger, settings

log = get_logger("security.tokens")


def get_or_create_token() -> str:
    path = settings.token_file
    if path.exists():
        value = path.read_text(encoding="utf-8").strip()
        if value:
            return value
    settings.ensure_dirs()
    token = secrets.token_urlsafe(16)
    path.write_text(token + "\n", encoding="utf-8")
    log.info("generated a new access token in %s", path.name)
    return token


def current_token() -> str:
    try:
        return settings.token_file.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def token_ok(supplied: str | None) -> bool:
    supplied = (supplied or "").strip()
    real = current_token()
    if not supplied or not real:
        return False
    return hmac.compare_digest(supplied, real)
