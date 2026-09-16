"""
Type the token once, never again — and no weaker than before.

The screens used to ask for the server address and token on every visit,
which made no sense once the server itself serves the screens. This checks
the replacement: supply the token once, the browser is remembered by an
HttpOnly cookie, and a stranger without either is still refused.

Run with:  python -m backend.tests.test_remember_device
"""

from __future__ import annotations

import sys

from fastapi.testclient import TestClient

from ..main import app
from ..security import sessions
from ..security.tokens import get_or_create_token
from . import expected

PASSED: list[str] = []
FAILED: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    (PASSED if ok else FAILED).append(f"{name}{(' — ' + detail) if detail else ''}")


def main() -> int:
    token = get_or_create_token()

    # --- a brand new browser --------------------------------------------
    with TestClient(app) as fresh:
        r = fresh.get("/api/v1/auth/session")
        check("a new browser is not remembered",
              r.status_code == 200 and r.json()["connected"] is False,
              str(r.json()))
        check("and cannot read data without the token",
              fresh.get("/proposals/load").status_code == 401)

    # --- supply the token once ------------------------------------------
    with TestClient(app) as browser:
        r = browser.post("/api/v1/auth/connect", json={"token": token})
        check("connecting with the right token succeeds",
              r.status_code == 200 and r.json().get("ok") is True, str(r.json()))
        check("the browser is now remembered",
              browser.get("/api/v1/auth/session").json()["connected"] is True)

        cookie = browser.cookies.get(sessions.DEVICE_COOKIE_NAME)
        check("a device cookie was set", bool(cookie))

        # THE POINT: no token in the URL, no header — just the cookie.
        r = browser.get("/proposals/load")
        want = expected.total_proposals()
        check("data loads with NO token supplied",
              r.status_code == 200 and len(r.json()["proposals"]) == want,
              f"HTTP {r.status_code}, {want} proposals")
        check("grants load with no token",
              browser.get("/hitlist-data/load").status_code == 200)
        check("clients load with no token",
              browser.get("/api/clients").status_code == 200)
        check("saving works with no token",
              browser.post("/proposals/save", json={"proposals": []}).status_code == 200)

        # --- and it can be undone ---------------------------------------
        browser.post("/api/v1/auth/forget")
        check("forgetting the device works",
              browser.get("/api/v1/auth/session").json()["connected"] is False)
        check("and data is refused again after forgetting",
              browser.get("/proposals/load").status_code == 401)

    # --- the wrong token still gets nowhere ------------------------------
    with TestClient(app) as bad:
        r = bad.post("/api/v1/auth/connect", json={"token": "not-the-token"})
        check("a wrong token is refused", r.status_code == 401, f"HTTP {r.status_code}")
        check("and no cookie is handed out",
              not bad.cookies.get(sessions.DEVICE_COOKIE_NAME))
        check("and data is still refused", bad.get("/proposals/load").status_code == 401)

    # --- a forged cookie is refused --------------------------------------
    with TestClient(app) as forger:
        forger.cookies.set(sessions.DEVICE_COOKIE_NAME, "eyJkZXYiOnRydWV9.notarealsignature")
        check("a forged cookie is refused",
              forger.get("/proposals/load").status_code == 401)
        check("and it does not count as remembered",
              forger.get("/api/v1/auth/session").json()["connected"] is False)

    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed\n")
    for line in PASSED:
        print("  PASS  " + line)
    for line in FAILED:
        print("  FAIL  " + line)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
