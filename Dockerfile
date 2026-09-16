# Bhumijo — proposal tracker + AI Agent, in one container.
#
# Built for the Synology NAS (Container Manager), but this is a plain Docker
# image and will run anywhere Docker runs.
#
# The point of running it this way: the container restarts itself when the NAS
# reboots, with nobody logged in. That is what "always on" actually needs.

FROM python:3.12-slim

# Keeps the image small and the logs live rather than buffered, so the
# container log shows what is happening as it happens.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Requirements first, on their own layer: rebuilds after a code change then
# skip the slow pip install entirely.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# The project itself.
COPY backend/   ./backend/
COPY app/       ./app/
COPY agent_free/ ./agent_free/
COPY frontend/  ./frontend/
COPY alembic/   ./alembic/
COPY tools/     ./tools/
COPY alembic.ini ./
COPY docker-entrypoint.sh ./

# Chart.js stored inside the image, so the screens draw their charts even if
# the NAS has no internet. Not fatal if it fails — the page falls back to the
# CDN — so the build is allowed to continue either way.
RUN python tools/vendor_chartjs.py || \
    echo "NOTE: Chart.js was not downloaded at build time; the page will fall back to the CDN."

# --- where the data lives ------------------------------------------------
# Both SQLite databases sit in /app/data, which is mounted from the NAS's own
# internal disk. That matters: SQLite needs a real local filesystem. It must
# never be pointed at a network share, or the database will fail to open.
#
# tender_agent.db normally sits in the project root; this moves it alongside
# bhumijo.db so ONE mounted folder holds everything and a backup of that
# folder is a complete backup.
ENV BHUMIJO_DATA_DIR=/app/data \
    BHUMIJO_LOG_DIR=/app/data/logs \
    BHUMIJO_BACKUP_DIR=/app/data/backups \
    TENDER_AGENT_DATABASE_URL=sqlite:////app/data/tender_agent.db \
    BHUMIJO_HOST=0.0.0.0 \
    BHUMIJO_PORT=8787 \
    BHUMIJO_ENV=production

RUN mkdir -p /app/data/logs /app/data/backups
VOLUME ["/app/data"]

EXPOSE 8787

# Container Manager shows this as the container's health, so a failure is
# visible in the NAS interface rather than only in the logs.
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request,sys; \
        sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8787/health', timeout=5).status==200 else 1)"

# Not CMD python directly: the AI Agent's Alembic migrations MUST run before
# the app starts, or the agent brings the whole server down on boot.
RUN chmod +x /app/docker-entrypoint.sh
ENTRYPOINT ["/app/docker-entrypoint.sh"]
