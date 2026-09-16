#!/usr/bin/env python3
"""
Is this machine able to host Bhumijo permanently?

Run this ON THE MACHINE you want to move Bhumijo to, BEFORE copying anything.
It changes nothing — it only looks and reports.

    python tools\\server_check.py

It answers, in order, the questions that actually decide whether the move
will work:

    1. What operating system is this?
    2. Is Python 3.10 or newer here?
    3. Is port 8787 free?
    4. Is there a local disk for the database? (a network share will not do)
    5. Can it reach the internet? (the AI Agent needs Anthropic and your mail)
    6. What is its address on the office network?
    7. Are the AI Agent's secrets set here?

Send the whole output back and it tells us exactly what still needs doing.
"""

from __future__ import annotations

import os
import platform
import socket
import sys
from pathlib import Path

PORT = 8787
LINE = "=" * 64

OK, WARN, BAD = "  [ OK ]", "  [WARN]", "  [FAIL]"

problems: list[str] = []
warnings: list[str] = []


def fail(msg: str) -> None:
    problems.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


def heading(text: str) -> None:
    print(f"\n{text}\n{'-' * len(text)}")


# --- 1. operating system ------------------------------------------------

def check_os() -> None:
    heading("1. Operating system")
    print(f"  {platform.system()} {platform.release()} ({platform.machine()})")
    print(f"  computer name: {platform.node()}")
    if platform.system() not in ("Windows", "Linux"):
        warn(f"unusual OS: {platform.system()}")


# --- 2. python ----------------------------------------------------------

def check_python() -> None:
    heading("2. Python")
    v = sys.version_info
    print(f"  Python {v.major}.{v.minor}.{v.micro}")
    print(f"  location: {sys.executable}")
    if (v.major, v.minor) < (3, 10):
        fail(f"Python {v.major}.{v.minor} is too old — 3.10 or newer is needed. "
             f"Install from python.org and tick 'Add Python to PATH'.")
    else:
        print(f"{OK} new enough")


# --- 3. the port --------------------------------------------------------

def check_port() -> None:
    heading(f"3. Port {PORT}")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.5)
        in_use = s.connect_ex(("127.0.0.1", PORT)) == 0
    if in_use:
        fail(f"something is already listening on port {PORT} here. Find out what, "
             f"or pick another port with BHUMIJO_PORT in .env")
    else:
        print(f"{OK} free")


# --- 4. a local disk ----------------------------------------------------

def check_disk() -> None:
    heading("4. Somewhere local to keep the database")
    here = Path(__file__).resolve().parent
    print(f"  this folder: {here}")

    if platform.system() == "Windows":
        drive = here.drive.upper()
        if str(here).startswith("\\\\"):
            fail("this folder is on a NETWORK SHARE. SQLite cannot run from one — "
                 "the database will fail to open or corrupt. Copy the project to a "
                 "local disk (C:\\ or D:\\) on this machine.")
        else:
            print(f"{OK} local disk {drive}")
    else:
        print(f"{OK} {here}")

    try:
        probe = here / ".write_probe"
        probe.write_text("x", encoding="utf-8")
        probe.unlink()
        print(f"{OK} this folder is writable")
    except OSError as exc:
        fail(f"cannot write here: {exc}")


# --- 5. internet --------------------------------------------------------

def check_internet() -> None:
    heading("5. Internet access (the AI Agent needs it)")
    targets = [("api.anthropic.com", 443, "Anthropic API — the AI Agent"),
               ("pypi.org", 443, "PyPI — needed to install the requirements")]
    for host, port, why in targets:
        try:
            with socket.create_connection((host, port), timeout=6):
                print(f"{OK} {host:22} reachable   ({why})")
        except OSError as exc:
            warn(f"cannot reach {host}: {exc} — {why}")
            print(f"{WARN} {host:22} NOT reachable  ({why})")


# --- 6. network address -------------------------------------------------

def check_address() -> None:
    heading("6. This machine's address on the office network")
    addresses = set()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            addresses.add(s.getsockname()[0])
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            addresses.add(info[4][0])
    except OSError:
        pass

    lan = sorted(a for a in addresses if not a.startswith("127."))
    if lan:
        for a in lan:
            print(f"  http://{a}:{PORT}")
        print("\n  ^ this is the address to share with everyone, once it is running")
    else:
        warn("could not work out this machine's network address")


# --- 7. the AI Agent's secrets ------------------------------------------

def check_secrets() -> None:
    heading("7. The AI Agent's settings")
    required = ["ANTHROPIC_API_KEY"]
    optional = ["GMAIL_APP_PASSWORD", "IMAP_APP_PASSWORD", "IMAP_HOST", "IMAP_PORT",
                "SMTP_HOST", "SMTP_PORT", "PROPOSAL_TRACKER_TOKEN"]

    for name in required:
        if os.environ.get(name):
            print(f"{OK} {name:24} is set")
        else:
            warn(f"{name} is NOT set here — the AI Agent will start but cannot "
                 f"call Claude. It must be set on this machine.")
            print(f"{WARN} {name:24} NOT set")

    for name in optional:
        state = "is set" if os.environ.get(name) else "not set"
        print(f"       {name:24} {state}")
    print("\n  (Values are never printed — only whether they exist.)")


def main() -> int:
    print(LINE)
    print("  Can this machine host Bhumijo permanently?")
    print(LINE)

    check_os()
    check_python()
    check_port()
    check_disk()
    check_internet()
    check_address()
    check_secrets()

    print(f"\n{LINE}")
    if problems:
        print("  MUST BE FIXED BEFORE MIGRATING:\n")
        for p in problems:
            print(f"   - {p}")
    if warnings:
        print("\n  WORTH KNOWING:\n")
        for w in warnings:
            print(f"   - {w}")
    if not problems and not warnings:
        print("  Everything checks out. This machine can host Bhumijo.")
    elif not problems:
        print("\n  Nothing blocking. The warnings above are worth sorting out,")
        print("  but the move can go ahead.")
    print(LINE)
    print("\n  Send this whole output back to Claude.\n")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
