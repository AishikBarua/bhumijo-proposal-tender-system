"""The single Jinja2Templates instance, shared by app.main and every route module.
Lives in its own module (not app.main) so routes can import it without app.main having
to import the routes first - a route module importing `from app.main import templates`
would be circular, since app.main imports and registers the routers.
"""
from datetime import timezone

from fastapi.templating import Jinja2Templates

from app.config import APP_TZ

templates = Jinja2Templates(directory="app/templates")


def _localtime(dt, fmt=None):
    """Jinja filter: converts a stored datetime to APP_TIMEZONE for display. Every
    DateTime column in this app stores UTC (see models.py) but SQLite drops tzinfo on
    round-trip, so a value loaded from the DB is naive-but-UTC - it's treated as UTC
    here regardless of whether .tzinfo happens to be set. Returns the converted
    datetime, or a formatted string if fmt is given: {{ some_dt|localtime('%d %b %H:%M') }}."""
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local_dt = dt.astimezone(APP_TZ)
    return local_dt.strftime(fmt) if fmt else local_dt


templates.env.filters["localtime"] = _localtime
