"""FastAPI application factory."""

from fastapi import FastAPI


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

    app.include_router(_health_router())

    from src.api.webhooks import router as webhooks_router

    app.include_router(webhooks_router)

    return app


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
