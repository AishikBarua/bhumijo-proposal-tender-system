"""
Does the rebuild actually fix the two problems it was meant to fix, and
leave everything else alone?

Run with:  python -m backend.tests.test_behaviour
"""

from __future__ import annotations

import sys

from fastapi.testclient import TestClient

from ..main import app
from ..security.tokens import get_or_create_token
from . import expected

PASSED: list[str] = []
FAILED: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASSED if condition else FAILED).append(f"{name}{(' — ' + detail) if detail else ''}")


def main() -> int:
    with TestClient(app) as c:
        token = get_or_create_token()
        headers = {"X-Auth-Token": token}
        q = f"?token={token}"

        original = c.get(f"/proposals/load{q}").json()["proposals"]
        start_count = len(original)

        # --- 1. the silent overwrite ----------------------------------
        # Two people, both holding a stale copy. Person A saves a list with
        # only ONE record in it — the old server would have deleted the
        # other 178 without a word.
        one_record = [dict(original[0])]
        c.post(f"/proposals/save{q}", json={"proposals": one_record})
        after = c.get(f"/proposals/load{q}").json()["proposals"]
        check(
            "a stale save no longer deletes everyone else's records",
            len(after) == start_count,
            f"{start_count} before, {len(after)} after (old system: would be 1)",
        )

        # --- 2. per-record editing ------------------------------------
        pid = original[0]["id"]
        was = c.get(f"/api/v1/proposals/{pid}{q}").json()["remark"]
        r = c.patch(f"/api/v1/proposals/{pid}{q}", json={"remark": "edited by the test"})
        check("one field can be changed on its own", r.status_code == 200, f"HTTP {r.status_code}")
        now = c.get(f"/api/v1/proposals/{pid}{q}").json()["remark"]
        check("the change actually landed", now == "edited by the test")
        others = c.get(f"/proposals/load{q}").json()["proposals"]
        check("editing one record left the rest alone", len(others) == start_count)

        # --- 3. the audit trail ---------------------------------------
        hist = c.get(f"/api/v1/proposals/{pid}/history{q}").json()["history"]
        check("the edit was recorded", len(hist) >= 1, f"{len(hist)} entry/entries")
        check(
            "the audit entry says what changed",
            any("remark" in (h.get("summary") or "") for h in hist),
            hist[0].get("summary", "") if hist else "no entries",
        )
        c.patch(f"/api/v1/proposals/{pid}{q}", json={"remark": was})

        # --- 4. validation --------------------------------------------
        bad = c.patch(f"/api/v1/proposals/{pid}{q}", json={"status": "Banana"})
        check("an invalid status is refused", bad.status_code in (400, 422),
              f"HTTP {bad.status_code}")
        bad_date = c.post(f"/api/v1/proposals{q}", json={
            "title": "T", "open_date": "2026-05-01", "close_date": "2026-01-01"})
        check("a close date before the open date is refused",
              bad_date.status_code in (400, 422), f"HTTP {bad_date.status_code}")

        # --- 5. authentication ----------------------------------------
        check("no token is refused", c.get("/proposals/load").status_code == 401)
        check("a wrong token is refused",
              c.get("/proposals/load?token=wrong").status_code == 401)

        # --- 6. the token is no longer downloadable -------------------
        # This was the critical hole: the old catch-all static handler
        # served any file next to the server, token file included.
        for path in ("/access_token.txt", "/proposal_access_token.txt",
                     "/data/access_token.txt", "/bhumijo.db",
                     "/data/bhumijo.db", "/backend/config/settings.py"):
            resp = c.get(path)
            check(f"{path} is not served", resp.status_code == 404,
                  f"HTTP {resp.status_code}")

        # --- 7. server-side filtering ---------------------------------
        fm = c.get(f"/api/v1/proposals{q}&entity=FM").json()
        want_fm = expected.proposals_in("FM")
        check("filtering happens on the server", fm["count"] == want_fm,
              f"{fm['count']} FM proposals, database holds {want_fm}")

        # --- 8. the figures -------------------------------------------
        s = c.get(f"/api/v1/proposals/summary{q}").json()
        check("win rate is computed", s["win_rate"] is not None, f"{s['win_rate']}%")
        want_won, want_lost = expected.won_and_lost()
        check("win rate matches the data",
              s["won"] == want_won and s["lost"] == want_lost,
              f"{s['won']} won, {s['lost']} lost")
        # Most proposals have no value recorded, and "N/A" correctly yields no
        # amount. The point is that the API reports the same split the
        # database holds — not a particular number.
        want_priced, want_unpriced = expected.priced_and_unpriced()
        check("unpriced records are reported honestly",
              s["unpriced_records"] == want_unpriced and s["priced_records"] == want_priced,
              f"{s['unpriced_records']} unpriced, {s['priced_records']} priced")

    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed\n")
    for line in PASSED:
        print("  PASS  " + line)
    for line in FAILED:
        print("  FAIL  " + line)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
