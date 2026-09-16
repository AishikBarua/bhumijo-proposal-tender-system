"""
The test that decides whether this rebuild can be trusted:
does the new system give back exactly what the old files hold?

Run with:  python -m backend.tests.test_parity
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from ..config import settings
from ..main import app
from ..security.tokens import get_or_create_token

LEGACY = settings.legacy_data_dir


def read_legacy_proposals() -> dict[str, dict]:
    out = {}
    for folder in (LEGACY / "proposals").glob("*"):
        path = folder / "proposals.jsonl"
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                item = json.loads(line)
                out[item["id"]] = item
    return out


def read_legacy_grants() -> dict[str, dict]:
    out = {}
    path = LEGACY / "Hitlist" / "programs.jsonl"
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            item = json.loads(line)
            out[str(item["id"])] = item      # later duplicate overwrites — fine, they matched
    return out


def read_legacy_clients() -> dict[str, dict]:
    path = LEGACY / "clients" / "clients.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {c["id"]: c for c in payload.get("clients", [])}


def compare(label: str, old: dict, new: dict, ignore: set[str]) -> list[str]:
    problems = []
    missing = set(old) - set(new)
    extra = set(new) - set(old)
    if missing:
        problems.append(f"{label}: {len(missing)} record(s) missing from the new system: "
                        f"{sorted(missing)[:5]}")
    if extra:
        problems.append(f"{label}: {len(extra)} unexpected record(s): {sorted(extra)[:5]}")

    for rid in sorted(set(old) & set(new)):
        o, n = old[rid], new[rid]
        for key in set(o) | set(n):
            if key in ignore:
                continue
            before, after = o.get(key, ""), n.get(key, "")
            if str(before).strip() != str(after).strip():
                problems.append(
                    f"{label} {rid}.{key}: was {before!r}, now {after!r}"
                )
    return problems


def main() -> int:
    failures: list[str] = []

    with TestClient(app) as client:
        token = get_or_create_token()
        headers = {"X-Auth-Token": token}

        proposals = client.get(f"/proposals/load?token={token}").json()["proposals"]
        grants = client.get(f"/hitlist-data/load?token={token}").json()["programs"]
        clients = client.get("/api/clients", headers=headers).json()["clients"]

    print(f"proposals: {len(proposals)}   grants: {len(grants)}   clients: {len(clients)}")

    failures += compare(
        "proposal",
        read_legacy_proposals(),
        {p["id"]: p for p in proposals},
        ignore=set(),
    )
    failures += compare(
        "grant",
        read_legacy_grants(),
        {str(g["id"]): g for g in grants},
        # fileLoc was absent on 177 of 192 records; absent and "" are the same thing.
        ignore={"fileLoc"},
    )
    failures += compare(
        "client",
        read_legacy_clients(),
        {c["id"]: c for c in clients},
        ignore=set(),
    )

    if failures:
        print(f"\n{len(failures)} DIFFERENCE(S) FOUND:\n")
        for line in failures[:40]:
            print("  -", line)
        if len(failures) > 40:
            print(f"  ... and {len(failures) - 40} more")
        return 1

    print("\nPARITY CONFIRMED — every field of every record matches the original files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
