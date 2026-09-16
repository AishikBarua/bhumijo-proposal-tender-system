"""
No token from the office network — and still locked from anywhere else.

Checks the trust_local_network setting does exactly what it claims:
office devices get straight in, public addresses do not, and turning the
setting off restores the token requirement completely.

Run with:  python -m backend.tests.test_trusted_network
"""

from __future__ import annotations

import sys

from fastapi.testclient import TestClient

from ..config import settings
from ..main import app
from . import expected

PASSED: list[str] = []
FAILED: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    (PASSED if ok else FAILED).append(f"{name}{(' — ' + detail) if detail else ''}")


def client_from(host: str) -> TestClient:
    """
    A client that appears to come from a particular address.

    Older Starlette accepted TestClient(client=(host, port)). The version
    this project pins (0.41.3) does not, so the address is injected into the
    ASGI scope instead — which is what the parameter did anyway.
    """
    client = TestClient(app)
    original = client.app

    async def with_client_address(scope, receive, send):
        if scope["type"] == "http":
            scope = dict(scope, client=(host, 50000))
        await original(scope, receive, send)

    client.app = with_client_address
    # portal/transport hold their own reference to the app, so replace it there too
    if hasattr(client, "_transport"):
        client._transport.app = with_client_address
    return client


OFFICE = ["127.0.0.1", "192.168.1.137", "192.168.1.50", "10.0.0.8", "172.16.4.2"]
OUTSIDE = ["8.8.8.8", "203.0.113.9", "51.15.22.7"]


def main() -> int:
    # --- from the office: nothing to type -------------------------------
    for host in OFFICE:
        with client_from(host) as c:
            r = c.get("/api/v1/auth/session")
            connected = r.status_code == 200 and r.json().get("connected") is True
            check(f"{host:15} connects with no token", connected,
                  r.json().get("reason", ""))

            d = c.get("/proposals/load")
            # Compared against the database, not a number typed in months ago.
            want = expected.total_proposals()
            check(f"{host:15} loads data with no token",
                  d.status_code == 200 and len(d.json()["proposals"]) == want,
                  f"HTTP {d.status_code}, {want} proposals")

    # --- from outside: token still required -----------------------------
    for host in OUTSIDE:
        with client_from(host) as c:
            r = c.get("/proposals/load")
            check(f"{host:15} is REFUSED without a token", r.status_code == 401,
                  f"HTTP {r.status_code}")
            s = c.get("/api/v1/auth/session")
            check(f"{host:15} is not reported as connected",
                  s.json().get("connected") is False)

    # --- with the setting off, the token is required everywhere ---------
    object.__setattr__(settings, "trust_local_network", False)
    try:
        for host in ["192.168.1.137", "127.0.0.1"]:
            with client_from(host) as c:
                r = c.get("/proposals/load")
                check(f"setting off: {host:15} needs the token again",
                      r.status_code == 401, f"HTTP {r.status_code}")
    finally:
        object.__setattr__(settings, "trust_local_network", True)

    # --- and it still works once turned back on -------------------------
    with client_from("192.168.1.137") as c:
        check("setting back on: office device connects again",
              c.get("/proposals/load").status_code == 200)

    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed\n")
    for line in PASSED:
        print("  PASS  " + line)
    for line in FAILED:
        print("  FAIL  " + line)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
