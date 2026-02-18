"""FastAPI application factory."""

import pathlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.config.settings import get_settings

FRONTEND_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI instance.
    """
    app = FastAPI(
        title="Ask Mary",
        description="AI clinical trial scheduling agent",
        version="0.1.0",
    )

    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(_health_router())

    from src.api.dashboard import router as dashboard_router
    from src.api.dashboard import ws_router
    from src.api.webhooks import router as webhooks_router
    from src.api.worker_routes import router as worker_router

    app.include_router(webhooks_router)
    app.include_router(dashboard_router)
    app.include_router(ws_router)
    app.include_router(worker_router)

    _mount_frontend(app)

    return app


def _mount_frontend(app: FastAPI) -> None:
    """Mount the React frontend static files if the dist directory exists.

    Serves index.html as the fallback for client-side routing.
    Must be mounted last so API routes take priority.

    Args:
        app: FastAPI application instance.
    """
    if FRONTEND_DIR.is_dir():
        app.mount(
            "/",
            StaticFiles(directory=str(FRONTEND_DIR), html=True),
            name="frontend",
        )


def _health_router() -> "fastapi.routing.APIRouter":
    """Create health check router.

    Returns:
        Router with health endpoints.
    """
    from fastapi import APIRouter

    router = APIRouter(tags=["health"])

    @router.get("/health")
    async def health() -> dict[str, str]:
        """Return application health status.

        Returns:
            Dict with status key.
        """
        return {"status": "ok"}

    return router


app = create_app()
