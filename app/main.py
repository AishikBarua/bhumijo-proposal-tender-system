"""App creation and router registration only - see app/routes/ for handlers,
app/services/ for business logic, app/config.py for env vars/constants (including
logging setup - importing app.database below pulls that in before anything here logs).

SUPERSEDED as a standalone entry point: this app is now mounted inside Bhumijo's
server (see backend/main.py, routers included with prefix="/agent") and started via
Bhumijo's start_server.bat, not start_agent.bat (retired). Templates and redirects
throughout app/ now hardcode the "/agent/..." prefix that only the merged server
provides, so running `python -m app.main` on its own (mounting bare "/" and
"/static") will show pages whose internal links 404. Kept only for reference /
local debugging of this app's own routes in isolation.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.routes import dashboard, tenders, settings, profile
from app.services.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler(app)
    yield
    stop_scheduler()


init_db()
app = FastAPI(title="Bhumijo Tender Agent", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(dashboard.router)
app.include_router(tenders.router)
app.include_router(settings.router)
app.include_router(profile.router)
