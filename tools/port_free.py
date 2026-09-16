#!/usr/bin/env python3
"""
Is the server's port free?

    exit code 0 — free, safe to start
    exit code 1 — something is already listening there

server_loop.bat calls this before every start. Without it, a second copy of
the server started by autostart would fight the first one for the port,
fail with [Errno 10048], and restart in a tight loop forever — silently,
because autostart runs with no window.
"""

from __future__ import annotations

import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from backend.config import settings
    PORT = settings.port
    HOST = "127.0.0.1"
except Exception:                      # noqa: BLE001 — fall back rather than fail
    PORT = 8787
    HOST = "127.0.0.1"


def something_is_listening(host: str, port: int, timeout: float = 1.5) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex((host, port)) == 0


def main() -> int:
    if something_is_listening(HOST, PORT):
        print(f"port {PORT} is already in use — a server is running")
        return 1
    print(f"port {PORT} is free")
    return 0


if __name__ == "__main__":
    sys.exit(main())
