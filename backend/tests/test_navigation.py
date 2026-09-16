"""
Every link the screens can follow must actually lead somewhere.

This exists because two navigation links were broken on first delivery: the
Grant button led to a page that had not been carried across, and the Proposal
button back from the hitlist led to the tracker's old filename, which the new
server did not serve. Both returned a bare {"detail":"Not Found"}.

Rather than fix them one at a time, this reads every internal navigation
target out of the frontend source and checks each one loads.

Run with:  python -m backend.tests.test_navigation
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from ..security.tokens import get_or_create_token

from ..config import settings
from ..main import app

FRONTEND = settings.frontend_dir

# Where the screens send the browser: window.location.href = '...'
NAV_PATTERN = re.compile(r"""location\.(?:href|assign|replace)\s*(?:=|\()\s*['"]([^'"]+)['"]""")

# ...and every link a person can click. This was missing at first, and three
# broken links reached the user because of it: the Grant button, the Proposal
# button back from the hitlist, and "Email settings" pointing at /agent/settings
# when the real route is /agent/email-settings. A test that only reads
# JavaScript misses every <a href> in a template.
HREF_PATTERN = re.compile(r'href="(/[^"#?]*)"')


# Every place a page can send someone: the browser screens, and both agents'
# server-rendered templates.
SEARCH_DIRS = [
    FRONTEND,
    FRONTEND.parent / "agent_free" / "templates",
    FRONTEND.parent / "app" / "templates",
]


def internal_targets() -> set[str]:
    targets: set[str] = set()
    for directory in SEARCH_DIRS:
        if not directory.exists():
            continue
        for path in list(directory.rglob("*.js")) + list(directory.rglob("*.html")):
            text = path.read_text(encoding="utf-8")

            for target in NAV_PATTERN.findall(text):
                if target.startswith(("http://", "https://", "//", "mailto:", "#")):
                    continue
                targets.add(target)

            for target in HREF_PATTERN.findall(text):
                # Skip anything Jinja builds at render time — the literal
                # "/agent/tender/{{ t.id }}" is not a real URL to check.
                if "{{" in target or "{%" in target:
                    continue
                targets.add(target)
    return targets


# Pages that must always load, links or not.
ALWAYS = {"/", "/hitlist", "/app/index.html"}


def main() -> int:
    targets = internal_targets()
    print(f"internal navigation targets found in the frontend: {len(targets)}")
    for t in sorted(targets):
        print(f"    {t}")

    to_check = sorted(ALWAYS | {"/" + t.lstrip("/") for t in targets})
    failures = []

        # The agent modules sit behind the shared token like every other
        # data route. TestClient's host is "testclient", not an IP, so the
        # trusted-network shortcut does not apply here and the token must
        # be supplied explicitly.
    with TestClient(app, headers={"X-Auth-Token": get_or_create_token()}) as client:
        print("\nchecking each one loads:")
        for path in to_check:
            response = client.get(path)
            # Pages must be HTML; stylesheets, scripts and images obviously
            # are not, so only require that they load at all.
            is_asset = path.rsplit(".", 1)[-1] in ("css", "js", "png", "jpg",
                                                   "svg", "ico", "woff", "woff2")
            ok = response.status_code == 200 and (
                is_asset or "text/html" in response.headers.get("content-type", ""))
            kind = "asset" if is_asset else "page "
            print(f"  {'PASS' if ok else 'FAIL'}  {kind} {path:44} HTTP {response.status_code}")
            if not ok:
                failures.append(path)

        # The fragments the shell pulls in must load too.
        print("\nchecking the page fragments the shell loads:")
        for name in ("dashboard", "proposals", "clients", "reports"):
            path = f"/app/pages/{name}/{name}.html"
            response = client.get(path)
            ok = response.status_code == 200 and len(response.text) > 100
            print(f"  {'PASS' if ok else 'FAIL'}  {path:45} HTTP {response.status_code}")
            if not ok:
                failures.append(path)

    if failures:
        print(f"\n{len(failures)} BROKEN LINK(S): {failures}")
        return 1
    print("\nevery internal link resolves.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
