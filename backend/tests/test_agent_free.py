"""
The no-API agent must find tenders, and must never call an API.

The second half matters as much as the first. "It works without a key" is
easy to believe and easy to get wrong — one forgotten import and it quietly
starts costing money, or starts failing for people with no key. So this test
replaces the Anthropic client with one that raises on contact: if any code
path reaches for it, the test fails and names the caller.

Run with:  python -m backend.tests.test_agent_free
"""

from __future__ import annotations

import sys

from fastapi.testclient import TestClient

from ..security.tokens import get_or_create_token

PASSED: list[str] = []
FAILED: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    (PASSED if ok else FAILED).append(f"{name}{(' — ' + detail) if detail else ''}")


DIGEST = """<html><body>
<a href="https://bdtender.com/notice/2001">View Notice</a>
<p><b>#1 2001</b> Construction of public toilet block at Mirpur 10 market<br>
Issue Date: 01/09/2026<br>Organization: Dhaka North City Corporation<br>
District: Dhaka<br>Document Price: 3000<br>
Doc Purchase Last Date: 20/09/2026<br>Submission Last Date: 28/09/2026</p>

<a href="https://bdtender.com/notice/2002">View Notice</a>
<p><b>#2 2002</b> Supply of stationery and printing materials<br>
Issue Date: 01/09/2026<br>Organization: Ministry of Education<br>
District: Dhaka<br>Document Price: 1000<br>
Doc Purchase Last Date: 18/09/2026<br>Submission Last Date: 25/09/2026</p>

<a href="https://bdtender.com/notice/2003">View Notice</a>
<p><b>#3 2003</b> টয়লেট নির্মাণ ও স্যানিটেশন উন্নয়ন প্রকল্প<br>
Issue Date: 02/09/2026<br>Organization: Khulna City Corporation<br>
District: Khulna<br>Document Price: 2500<br>
Doc Purchase Last Date: 21/09/2026<br>Submission Last Date: 29/09/2026</p>
</body></html>"""


def main() -> int:
    # --- make any API call explode, before importing the app --------------
    calls: list[str] = []

    try:
        import anthropic

        class Exploding:
            def __init__(self, *a, **k):
                pass

            def __getattr__(self, name):
                import traceback
                calls.append("".join(traceback.format_stack()[-4:-1]))
                raise AssertionError(
                    "The no-API agent tried to reach Anthropic. It must not.")

        anthropic.Anthropic = Exploding  # type: ignore[assignment]
    except ImportError:
        pass  # no anthropic installed is fine — that is the point

    from ..main import app
    from app.database import SessionLocal
    from app.models import Tender
    from agent_free import keywords as kw
    from agent_free.services import pipeline

        # The agent modules sit behind the shared token like every other
        # data route. TestClient's host is "testclient", not an IP, so the
        # trusted-network shortcut does not apply here and the token must
        # be supplied explicitly.
    with TestClient(app, follow_redirects=True,
                    headers={"X-Auth-Token": get_or_create_token()}) as client:
        # --- the screens exist -------------------------------------------
        for path in ("/agent-free/", "/agent-free/keywords", "/agent-free/paste"):
            check(f"{path} loads", client.get(path).status_code == 200)

        # --- it finds the right listings ---------------------------------
        # Clear anything a previous run left behind. Without this the test
        # passes once on a fresh database and then fails for ever after,
        # because the dedup correctly refuses to add the same refs twice —
        # which looks like a bug in the agent when it is a bug in the test.
        setup = SessionLocal()
        setup.query(Tender).filter(Tender.source == "rules").delete()
        setup.commit()
        setup.close()
        start = 0

        response = client.post("/agent-free/paste", data={"digest": DIGEST})
        check("a pasted digest is processed", response.status_code == 200)

        db = SessionLocal()
        rows = db.query(Tender).filter(Tender.source == "rules").all()
        added = len(rows) - start
        check("kept 2 of 3 listings", added == 2, f"kept {added}")

        titles = " ".join(t.title or "" for t in rows)
        check("kept the English toilet tender", "Mirpur 10" in titles)
        check("kept the Bengali sanitation tender", "টয়লেট" in titles)
        check("rejected the stationery tender", "stationery" not in titles.lower())

        saved = [t for t in rows if t.tender_ref == "2001"]
        if saved:
            t = saved[0]
            check("deadline parsed", str(t.deadline_date) == "2026-09-28",
                  str(t.deadline_date))
            check("organisation captured", t.organization == "Dhaka North City Corporation")
            check("document price captured", t.document_price == "3000")
            check("notice link captured", bool(t.notice_url))
            check("marked as rule-found, not AI", t.source == "rules")
            check("eligibility honestly marked unchecked",
                  t.hard_filter_pass is None and "not checked" in
                  (t.hard_filter_reason or "").lower())
        else:
            check("the toilet tender was saved", False, "not found")

        # --- running it twice must not duplicate --------------------------
        client.post("/agent-free/paste", data={"digest": DIGEST})
        again = db.query(Tender).filter(Tender.source == "rules").count()
        check("re-processing the same digest adds nothing",
              again == len(rows), f"{again} rows after second run")

        # --- keywords are editable and take effect ------------------------
        original = kw.load()
        try:
            kw.save(kw.KeywordSet(english=["nothing-matches-this"],
                                  bengali=[], exclude=[]))
            result = kw.check("Construction of public toilet block")
            check("editing the keywords changes the outcome", not result.relevant)
        finally:
            kw.save(original)
        check("keywords restored", kw.check("public toilet").relevant)

        # --- the rest of the system is untouched --------------------------
        # TestClient reports its host as "testclient", which is not an IP, so
        # the trusted-network check correctly refuses it. Supply the token
        # instead — the point here is that the tracker still answers at all.
        token = get_or_create_token()
        check("the tracker still works",
              client.get(f"/proposals/load?token={token}").status_code == 200)
        check("the AI Agent is still there", client.get("/agent/").status_code == 200)

        db.close()

    # --- the whole point ---------------------------------------------------
    check("NO API call was made at any point", not calls,
          f"{len(calls)} call(s)" if calls else "zero")

    from app.database import SessionLocal as S
    db = S()
    try:
        from app.models import UsageLog
        real = db.query(UsageLog).filter(UsageLog.model != "x").count()
        check("nothing was logged as billable usage", real == 0, f"{real} rows")
    except Exception:
        pass
    finally:
        db.close()

    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed\n")
    for line in PASSED:
        print("  PASS  " + line)
    for line in FAILED:
        print("  FAIL  " + line)
    if calls:
        print("\n  An API call came from:\n" + calls[0])
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
