"""Every environment variable and cross-module constant this app uses, in one place.

Read environment variables HERE ONLY - every other module imports the resolved value
from this module rather than calling os.environ.get() itself. That makes "what does
this app read from the environment" a single grep instead of a hunt across files, and
keeps env var defaults from silently drifting between two copies.

Values are resolved once, at import time (matching how ai.py always did it) - this app
is started once per process (see docs/AUTOSTART.md) and never needs to notice an
environment variable changing without a restart.

Secrets (ANTHROPIC_API_KEY, IMAP_APP_PASSWORD) are never logged by value anywhere in
this app - app.services.scheduler logs presence only ('present'/'MISSING') once at
startup, reading the resolved values below.

Logging is configured here (not in app.main) so it's in effect as early as possible:
almost every module imports something from this file, so by the time any of them call
logging.getLogger(...), the format/level below is already active.
"""
import logging
import os
from pathlib import Path
from zoneinfo import ZoneInfo

# Absolute project root (the folder this app's own project used to live at on
# its own — now a subfolder of the merged Bhumijo project). Computed from this
# file's own location rather than assumed from cwd, so paths below are correct
# regardless of what directory the merged server is launched from.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# --- Secrets - see docs/SECURITY.md. Never logged by value. ---
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
IMAP_APP_PASSWORD = os.environ.get("IMAP_APP_PASSWORD")  # None if unset - see app.services.credentials
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")  # deprecated fallback (was Gmail; mailbox is now Zoho) - see app.services.credentials

# --- Timezone. Bangladesh is UTC+6 - the database always stores UTC (see models.py);
# this is only for display and for "local calendar day" arithmetic (deadline countdowns,
# the IMAP SINCE date) where using UTC would be wrong near midnight. ---
APP_TIMEZONE = os.environ.get("APP_TIMEZONE", "Asia/Dhaka")
APP_TZ = ZoneInfo(APP_TIMEZONE)

# --- Logging ---
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(module)s: %(message)s",
)

# --- AI models (app.services.ai) - see README for the cost rationale ---
ANTHROPIC_MODEL_CHEAP = os.environ.get("ANTHROPIC_MODEL_CHEAP", "claude-haiku-4-5-20251001")
ANTHROPIC_MODEL_CAPABLE = os.environ.get("ANTHROPIC_MODEL_CAPABLE", "claude-sonnet-5")
RAW_TEXT_CAP = 15000  # chars - a long pasted/PDF notice otherwise costs ~10x a normal one
CLASSIFICATION_SNIPPET_CAP = 1000  # chars - Stage 1 (is_tender_email) sends only this much of the body

# --- IMAP (app.services.email_intake) / SMTP (app.services.notify). Mailbox is Zoho
# (info@bhumijo.com) as of 2026-08; overridable via env if the mailbox moves again -
# not secrets, so safe to include in the startup log line. ---
IMAP_HOST = os.environ.get("IMAP_HOST", "imappro.zoho.com")
IMAP_PORT = int(os.environ.get("IMAP_PORT", "993"))
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.zoho.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))

# --- Automated pipeline fetch (app.services.pipeline) ---
FETCH_MAX_RESULTS = 50
FETCH_SINCE_DAYS = 3

# --- Database (app.database, alembic/env.py) ---
# Absolute, not "sqlite:///./tender_agent.db" - that was only ever correct
# because start_agent.bat happened to cd into this folder first. Now that this
# app is merged into Bhumijo's server (started from the Bhumijo project root),
# an absolute path removes the dependency on the launcher's cwd entirely.
DATABASE_URL = os.environ.get(
    "TENDER_AGENT_DATABASE_URL",
    f"sqlite:///{_PROJECT_ROOT / 'tender_agent.db'}",
)

# --- Server (app.main, app.services.notify) ---
# This app no longer runs its own uvicorn process (see start_agent.bat, now
# retired) - it is mounted inside Bhumijo's server under the /agent prefix.
# SERVER_PORT / DASHBOARD_URL follow Bhumijo's own settings so links in status
# emails point at the merged address instead of the old standalone port 8000.
SERVER_PORT = int(os.environ.get("BHUMIJO_PORT", "8787"))
DASHBOARD_URL = os.environ.get("AGENT_DASHBOARD_URL", f"http://localhost:{SERVER_PORT}/agent")

# --- Proposal Tracker sync (app.services.proposal_tracker). Fires when a tender is
# marked "selected" - this app has no formal "Approved" status; "selected" is the
# closest equivalent (the point a human decides to pursue the tender). Token is a
# secret, never logged by value - see docs/SECURITY.md. ---
PROPOSAL_TRACKER_URL = os.environ.get("PROPOSAL_TRACKER_URL", "http://127.0.0.1:8585/proposals/from-agent")
PROPOSAL_TRACKER_TOKEN = os.environ.get("PROPOSAL_TRACKER_TOKEN", "")
