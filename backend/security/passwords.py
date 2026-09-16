"""
Password hashing. Standard library only — no extra install on the office PC.

PBKDF2-HMAC-SHA256 with a per-password salt. A stolen database gives an
attacker hashes, not passwords, which is the whole point.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 240_000
SALT_BYTES = 16


def hash_password(password: str, *, iterations: int = ITERATIONS) -> str:
    if not password or len(password) < 8:
        raise ValueError("a password must be at least 8 characters")
    salt = secrets.token_hex(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
    ).hex()
    return f"{ALGORITHM}${iterations}${salt}${digest}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored or not password:
        return False
    try:
        algorithm, iterations, salt, expected = stored.split("$", 3)
    except ValueError:
        return False
    if algorithm != ALGORITHM:
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations)
    ).hex()
    # Constant time — a timing difference is a real leak.
    return hmac.compare_digest(digest, expected)


def needs_rehash(stored: str | None) -> bool:
    if not stored:
        return True
    try:
        algorithm, iterations, _, _ = stored.split("$", 3)
    except ValueError:
        return True
    return algorithm != ALGORITHM or int(iterations) < ITERATIONS
