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
        return {"status": "ok"}

    return router


app = create_app()
