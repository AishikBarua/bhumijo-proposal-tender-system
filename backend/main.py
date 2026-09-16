#!/usr/bin/env python3
"""
Wires the parts together and starts the server. That is all this file does —
no routes, no rules, no SQL.

    python -m backend.main
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import ROUTERS
from .api.deps import require_token
from .config import configure_logging, get_logger, settings
from .database.connection import get_connection, run_migrations
from .jobs import scheduler
from .security.permissions import Forbidden
from .security.tokens import get_or_create_token

# --- AI Agent module (formerly the standalone tender-agent project, its own
# server on port 8000 - see app/main.py's docstring). Merged in as an ordinary
# Python package (app/), mounted below under the "/agent" prefix. Its own
# routes/templates hardcode that prefix, so it only works served this way. ---
from app.database import init_db as agent_init_db
from app.routes import dashboard as agent_dashboard
from app.routes import profile as agent_profile
from app.routes import settings as agent_settings
from app.routes import tenders as agent_tenders
from app.services.scheduler import start_scheduler as agent_start_scheduler
from app.services.scheduler import stop_scheduler as agent_stop_scheduler

# --- Tender Finder, the no-API version (agent_free/) ------------------
# Same job as the AI Agent but by keyword matching instead of Claude, so it
# costs nothing and works with no API key. Mounted separately at
# /agent-free; the two share tender_agent.db and are otherwise independent.
from agent_free.routes import dashboard as free_dashboard
from agent_free.services import scheduler as free_scheduler

configure_logging()
log = get_logger("main")


def _bridge_agent_logging() -> None:
    """Sends the AI Agent's own log lines (logger name "tender_agent") through
    Bhumijo's existing console + rotating-file handlers, so they land in the same
    place as everything else instead of only reaching a console window that
    autostart hides. Without this, agent logs would depend on the stdlib root
    logger's default handler (set up by app/config.py's logging.basicConfig()),
    which never writes to a file."""
    bhumijo_logger = logging.getLogger("bhumijo")
    agent_logger = logging.getLogger("tender_agent")
    agent_logger.handlers = list(bhumijo_logger.handlers)
    agent_logger.setLevel(bhumijo_logger.level)
    agent_logger.propagate = False


def get_lan_ip() -> str:
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def write_info_file(ip: str, token: str) -> None:
    settings.ensure_dirs()
    path = settings.data_dir / "SERVER_INFO.txt"
    path.write_text(
        f"{settings.app_name} — v{settings.version}\n"
        f"{'=' * 60}\n"
        f"On this PC:               http://localhost:{settings.port}\n"
        f"On the office network:    http://{ip}:{settings.port}\n"
        f"API documentation:        http://localhost:{settings.port}/docs\n\n"
        f"Access token:             {token}\n\n"
        f"Database:                 {settings.database_path}\n"
        f"Backups:                  {settings.backup_dir}\n\n"
        f"This file is rewritten every time the server starts.\n",
        encoding="utf-8",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_dirs()
    run_migrations()

    token = get_or_create_token()
    ip = get_lan_ip()
    write_info_file(ip, token)

    counts = get_connection().execute(
        """
        SELECT (SELECT COUNT(*) FROM proposals)        AS proposals,
               (SELECT COUNT(*) FROM grant_programmes) AS grants,
               (SELECT COUNT(*) FROM clients)          AS clients
        """
    ).fetchone()

    log.info("=" * 60)
    log.info("%s v%s (%s)", settings.app_name, settings.version, settings.environment)
    log.info("On this PC:            http://localhost:%d", settings.port)
    log.info("On the office network: http://%s:%d", ip, settings.port)
    log.info("API documentation:     http://localhost:%d/docs", settings.port)

    # Printed straight to the console rather than logged, so it is on screen
    # where you need it but does not end up sitting in the rotating log file.
    print(f"\n  ACCESS TOKEN:  {token}")
    print(f"  Paste this into the 'Server Connection' box in the sidebar.")
    print(f"  Also saved in: {settings.data_dir / 'SERVER_INFO.txt'}\n", flush=True)

    log.info("Holding %d proposals, %d grant programmes, %d clients",
             counts["proposals"], counts["grants"], counts["clients"])
    if not counts["proposals"]:
        log.warning("the database is empty — run: python -m backend.migrate")
    log.info("=" * 60)

    # AI Agent module startup - own DB (checked against its own Alembic head,
    # never altered here), own APScheduler instance for its email-intake polling.
    # A second independent BackgroundScheduler in this process is fine; each one
    # only knows about its own jobs.
    _bridge_agent_logging()
    agent_init_db()
    agent_start_scheduler(app)
    log.info("AI Agent module ready at /agent")

    free_scheduler.start()
    log.info("Tender Finder (no API) ready at /agent-free")

    scheduler.start()
    try:
        yield
    finally:
        scheduler.stop()
        agent_stop_scheduler()
        log.info("server stopped")


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description=(
        "Proposal and grant tracking. The /api/v1 endpoints are the real ones; "
        "everything without a version prefix exists so the current screens keep "
        "working unchanged, and goes away once they have moved over."
    ),
    lifespan=lifespan,
)

# An explicit list, never "*". With no origins configured the screens are
# served from this same server, which needs no CORS at all.
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Auth-Token"],
    )
    log.info("CORS allowed for: %s", ", ".join(settings.cors_origins))


@app.exception_handler(Forbidden)
async def _forbidden(request: Request, exc: Forbidden) -> JSONResponse:
    return JSONResponse({"ok": False, "error": str(exc)}, status_code=403)


for router in ROUTERS:
    app.include_router(router)

# The agent modules were written as standalone apps and carry no auth of
# their own. Mounted here they are part of this server, so they go behind
# the same door as everything else: on the office network require_token
# returns immediately, from anywhere else it demands the shared token.
AUTHENTICATED = [Depends(require_token)]

app.include_router(free_dashboard.router, dependencies=AUTHENTICATED)

# AI Agent module - same prefix its templates/redirects already hardcode.
for agent_router in (agent_dashboard.router, agent_tenders.router,
                     agent_settings.router, agent_profile.router):
    app.include_router(agent_router, prefix="/agent", dependencies=AUTHENTICATED)


# --- the screens ------------------------------------------------------
# Only what is inside the frontend folder is ever served. There is no
# catch-all handler, so no request can reach the token file, the database
# or anything else sitting beside the code.

FRONTEND = settings.frontend_dir


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(FRONTEND / "index.html")


GRANTS_PAGE = FRONTEND / "pages" / "grants" / "hitlist.html"


@app.get("/hitlist", include_in_schema=False)
async def hitlist() -> FileResponse:
    """The grant hitlist screen."""
    return FileResponse(GRANTS_PAGE)


# The two screens still navigate to each other by their original filenames —
# the Grant button on the tracker, and the Proposal button on the hitlist.
# Both are served here so the round trip works and old bookmarks keep working.
# These routes disappear once the hitlist becomes a module of the shell.
# backend/tests/test_navigation.py checks every internal link still resolves.

@app.get("/bhumijo-Hitlist-22Jul2026.html", include_in_schema=False)
async def hitlist_legacy_filename() -> FileResponse:
    return FileResponse(GRANTS_PAGE)


@app.get("/Bhumijo_Proposal_Tracker_22Jul2026.html", include_in_schema=False)
async def tracker_legacy_filename() -> FileResponse:
    return FileResponse(FRONTEND / "index.html")


@app.middleware("http")
async def _no_stale_frontend(request: Request, call_next):
    """
    Stop the browser serving a cached copy of the screens.

    Chrome will happily reuse a months-old .js file, which meant a fix could
    be live on the server while the person in front of the screen still saw
    the old behaviour — and no amount of restarting the server changed it.
    The files are small and local, so revalidating every time costs nothing.
    """
    response = await call_next(request)
    if (request.url.path.startswith("/app/")
            or request.url.path == "/"
            or request.url.path.endswith(".html")):
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    return response


if FRONTEND.exists():
    app.mount("/app", StaticFiles(directory=FRONTEND, html=True), name="frontend")

AGENT_STATIC = Path(__file__).resolve().parent.parent / "app" / "static"
if AGENT_STATIC.exists():
    app.mount("/agent/static", StaticFiles(directory=AGENT_STATIC), name="agent-static")


def main() -> int:
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        log_config=None,
        access_log=False,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
