"""
Signed session cookies. Scaffolded now; switched on when logins land.

A session is a signed statement of "this is user N, until this time". The
signature means the browser cannot edit it, and no session state has to be
kept on the server.
"""

from __future__ import annotations

import base64
import hmac
import json
import secrets
import time
from hashlib import sha256

from ..config import get_logger, settings

log = get_logger("security.sessions")

COOKIE_NAME = "bhumijo_session"

# A separate, longer-lived cookie that just says "this browser has already
# proved it knows the shared token". It is what stops people retyping the
# token on every visit. HttpOnly, so page scripts cannot read it — which
# makes it safer than keeping the token in localStorage, where anything
# running on the page could pick it up.
DEVICE_COOKIE_NAME = "bhumijo_device"
DEVICE_DAYS = 90


def _secret() -> bytes:
    path = settings.session_secret_file
    if path.exists():
        value = path.read_text(encoding="utf-8").strip()
        if value:
            return value.encode("utf-8")
    settings.ensure_dirs()
    value = secrets.token_urlsafe(32)
    path.write_text(value + "\n", encoding="utf-8")
    log.info("generated a new session secret in %s", path.name)
    return value.encode("utf-8")


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def issue(user_id: int, username: str, *, hours: int | None = None) -> str:
    hours = hours or settings.session_hours
    payload = {
        "uid": user_id,
        "usr": username,
        "exp": int(time.time()) + hours * 3600,
    }
    body = _b64(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _b64(hmac.new(_secret(), body.encode("ascii"), sha256).digest())
    return f"{body}.{signature}"


def issue_device(days: int | None = None) -> str:
    """Remember that this browser has already supplied the shared token."""
    days = days or DEVICE_DAYS
    payload = {"dev": True, "exp": int(time.time()) + days * 86400}
    body = _b64(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _b64(hmac.new(_secret(), body.encode("ascii"), sha256).digest())
    return f"{body}.{signature}"


def device_ok(cookie: str | None) -> bool:
    payload = read(cookie)
    return bool(payload and payload.get("dev"))


def read(cookie: str | None) -> dict | None:
    if not cookie or "." not in cookie:
        return None
    body, _, signature = cookie.rpartition(".")
    expected = _b64(hmac.new(_secret(), body.encode("ascii"), sha256).digest())
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        payload = json.loads(_unb64(body))
    except (ValueError, json.JSONDecodeError):
        return None
    if payload.get("exp", 0) < time.time():
        return None
    return payload
