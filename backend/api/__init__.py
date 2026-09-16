from . import audit, auth, clients, grants, legacy, proposals, reference, reports

ROUTERS = [
    legacy.router,        # the nine endpoints today's screens call
    auth.router,
    proposals.router,
    grants.router,
    clients.router,
    reports.router,
    reference.router,
    audit.router,
]

__all__ = ["ROUTERS"]
