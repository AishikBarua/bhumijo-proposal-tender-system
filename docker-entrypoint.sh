#!/bin/sh
# Runs every time the container starts.
#
# The AI Agent's database is managed by Alembic. If its migrations have not
# been applied, the agent raises "no such table: email_settings" during
# startup and takes the WHOLE server down with it - the tracker included.
# So the migrations run first, every time. Applying them when they are
# already applied does nothing, so this is safe on every restart.

set -e

echo "[entrypoint] applying AI Agent database migrations..."
if alembic upgrade head; then
    echo "[entrypoint] agent database is up to date"
else
    echo "[entrypoint] ERROR: could not apply the agent migrations - stopping."
    echo "[entrypoint] The server is NOT started, because it would crash on"
    echo "[entrypoint] startup anyway. Check the message above."
    exit 1
fi

echo "[entrypoint] starting Bhumijo..."
exec python -m backend.main
