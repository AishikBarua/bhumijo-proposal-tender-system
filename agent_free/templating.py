"""Jinja setup for the no-API agent's own templates.

Its own instance rather than reusing app.templating, so the two agents cannot
break each other's pages — but it borrows the same localtime filter so dates
read identically across both.
"""

from fastapi.templating import Jinja2Templates

from app.templating import _localtime

templates = Jinja2Templates(directory="agent_free/templates")
templates.env.filters["localtime"] = _localtime
