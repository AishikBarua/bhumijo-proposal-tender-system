"""
The architecture, enforced rather than described.

The folder diagram says each layer may only call the one below it:

    api/        routes only — no SQL, no business rules
    security/   the guard
    services/   the business rules — must not know it is being called over HTTP
    models/     the shapes — must not touch the database
    database/   the only place SQL is written
    jobs/       scheduled work
    config/     settings — no addresses or paths written in code

A diagram in a document drifts the moment someone is in a hurry. This test
fails the build instead. It was written after exactly that happened: the
login code was querying `users` and `roles` straight from api/auth.py and
api/deps.py, and nothing noticed for a week.

Run with:  python -m backend.tests.test_architecture
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent

PASSED: list[str] = []
FAILED: list[str] = []


def check(name: str, offenders: list[str], detail: str = "") -> None:
    if offenders:
        FAILED.append(f"{name} — {', '.join(offenders)}")
    else:
        PASSED.append(f"{name}{(' — ' + detail) if detail else ''}")


def python_files(folder: str) -> list[Path]:
    return sorted(p for p in (BACKEND / folder).rglob("*.py") if p.name != "__init__.py")


def source(path: Path) -> str:
    """File contents with comments and docstrings stripped.

    Without this, a comment that merely mentions SELECT would fail the test —
    and the honest fix for that is to read code, not to weaken the pattern.
    """
    text = path.read_text(encoding="utf-8")
    text = re.sub(r'"""(?:.|\n)*?"""', "", text)
    text = re.sub(r"'''(?:.|\n)*?'''", "", text)
    text = re.sub(r"#.*", "", text)
    return text


# No trailing \b here: a group ending in \w followed by \b only matches a
# SINGLE-letter identifier, so "SELECT id" slipped through. That bug made this
# whole test pass on code it should have failed — found by deliberately
# planting a violation and watching it not fire.
SQL = re.compile(r"\b(SELECT\s+\w|INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM)", re.I)


def main() -> int:
    # --- 1. routes must not write SQL -----------------------------------
    offenders = [p.name for p in python_files("api") if SQL.search(source(p))]
    check("api/ writes no SQL", offenders, f"{len(python_files('api'))} route files")

    # --- 2. business rules must not know about HTTP ----------------------
    offenders = [
        p.name for p in python_files("services")
        if re.search(r"^\s*(from fastapi|import fastapi|from starlette)", source(p), re.M)
    ]
    check("services/ does not import FastAPI", offenders)

    # --- 3. shapes must not touch storage --------------------------------
    offenders = [
        p.name for p in python_files("models")
        if re.search(r"\b(sqlite3|get_connection|repositories)\b", source(p))
        or SQL.search(source(p))
    ]
    check("models/ does not touch the database", offenders)

    # --- 4. SQL lives only in the database layer -------------------------
    allowed = {"repositories", "connection.py", "audit_log.py", "migrate.py"}
    offenders = []
    for folder in ("api", "security", "services", "models", "jobs", "config"):
        for path in python_files(folder):
            if SQL.search(source(path)):
                offenders.append(f"{folder}/{path.name}")
    check("SQL confined to database/", offenders)

    # --- 5. no hardcoded ports, hosts or drive letters -------------------
    # Every address belongs in config/. This is what let the project move
    # between machines and networks without a code change.
    pattern = re.compile(r"(\b8787\b|\b8585\b|\b8000\b|[A-Z]:\\\\|\b192\.168\.\d)")
    offenders = []
    for folder in ("api", "security", "services", "models", "jobs", "database"):
        for path in python_files(folder):
            # deps.py legitimately lists the private network ranges it trusts
            if path.name == "deps.py":
                continue
            if pattern.search(source(path)):
                offenders.append(f"{folder}/{path.name}")
    check("no ports or paths hardcoded outside config/", offenders)

    # --- 6. every folder the diagram promises actually exists ------------
    missing = [
        name for name in
        ("api", "security", "services", "models", "database", "jobs", "config")
        if not (BACKEND / name).is_dir() or not python_files(name)
    ]
    check("all seven backend folders exist and are populated", missing)

    # --- 7. the frontend folders too -------------------------------------
    frontend = BACKEND.parent / "frontend"
    expected = ["pages/dashboard", "pages/proposals", "pages/grants",
                "pages/clients", "pages/reports", "services", "resources"]
    missing = [d for d in expected
               if not any((frontend / d).glob("*")) if (frontend / d).exists() or True]
    missing = [d for d in expected if not (frontend / d).exists()
               or not any((frontend / d).iterdir())]
    check("frontend folders exist and are populated", missing)

    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed\n")
    for line in PASSED:
        print("  PASS  " + line)
    for line in FAILED:
        print("  FAIL  " + line)

    if FAILED:
        print("\n  The folder structure and the code have drifted apart.")
        print("  Move the offending code into the layer it belongs in —")
        print("  do not weaken this test.")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
