"""FastAPI application factory."""

from __future__ import annotations

import pathlib
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi import APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.config.settings import get_settings

FRONTEND_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown lifecycle.

    Starts the in-memory Cloud Tasks executor on startup and
    stops it cleanly on shutdown.

    Args:
        app: FastAPI application instance.

    Yields:
        Control to the running application.
    """
    from src.services.cloud_tasks_client import (
        start_task_executor,
        stop_task_executor,
    )

    await start_task_executor()
    yield
    await stop_task_executor()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI instance.
    """
    app = FastAPI(
        title="Ask Mary",
        description="AI clinical trial scheduling agent",
        version="0.1.0",
        lifespan=_lifespan,
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

    _wire_validator_db_access()

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


def _wire_validator_db_access() -> None:
    """Wire the validator DB stub to the real Postgres implementation.

    Fixes KI-8: validators.get_participant_by_id was a stub that raised
    NotImplementedError. This replaces it with the real DB lookup at
    app startup.
    """
    import src.shared.validators as validators_module
    from src.db.postgres import get_participant_by_id as db_get_participant

    validators_module.get_participant_by_id = db_get_participant  # type: ignore[assignment]


def _health_router() -> APIRouter:
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
