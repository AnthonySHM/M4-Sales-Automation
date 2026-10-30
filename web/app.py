"""web.app — FastAPI application factory for M4 Sales Automation.

Entry point: create_app() returns a configured FastAPI instance.
No module-level app instantiation; import has no side effects (TL-15).

Architecture refs: AD-15 (FastAPI), AD-19 (Jinja2), G-22 (health endpoint).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import pathlib

from web.routes.auth import router as _auth_router

_PACKAGE_DIR = pathlib.Path(__file__).parent


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Lifespan hook — startup and shutdown logic goes here in future tasks."""
    # Startup: nothing needed yet (Drive / ledger integration deferred to #38+)
    yield
    # Shutdown: nothing needed yet


def create_app() -> FastAPI:
    """Application factory.

    Returns a fully-configured FastAPI instance.  Calling this function has no
    side effects beyond constructing the app object — no network I/O, no Google
    API calls, no sys.exit (TL-15).
    """
    app = FastAPI(
        title="M4 Sales Automation",
        version="0.1.0",
        lifespan=_lifespan,
    )

    # Mount static files
    app.mount(
        "/static",
        StaticFiles(directory=str(_PACKAGE_DIR / "static")),
        name="static",
    )

    # Jinja2 templates — stored under web/templates/
    templates = Jinja2Templates(directory=str(_PACKAGE_DIR / "templates"))

    # Store templates on app.state so routes added in future tasks can access them
    app.state.templates = templates

    # ------------------------------------------------------------------
    # Routers
    # ------------------------------------------------------------------

    app.include_router(_auth_router)

    from web.routes.jobs import router as _jobs_router
    app.include_router(_jobs_router)

    # ------------------------------------------------------------------
    # Middleware
    # ------------------------------------------------------------------

    from web.middleware import RoleEnforcementMiddleware
    app.add_middleware(RoleEnforcementMiddleware)

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------

    @app.get("/health")
    async def health():
        """Liveness probe — returns {"status": "ok"} with HTTP 200 (G-22)."""
        return {"status": "ok"}

    return app
