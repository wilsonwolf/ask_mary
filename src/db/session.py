"""Async database session factory for Cloud SQL Postgres."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config.settings import get_settings

_engine = None
_session_factory = None


def _get_engine():
    """Create or return the cached async engine.

    Returns:
        AsyncEngine connected to Cloud SQL via Auth Proxy.
    """
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=False,
            pool_size=5,
            max_overflow=10,
        )
    return _engine


def _get_session_factory():
    """Create or return the cached session factory.

    Returns:
        Async session factory bound to the engine.
    """
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=_get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session with auto-commit.

    Commits on successful completion, rolls back on exception.

    Yields:
        AsyncSession that commits on success.
    """
    factory = _get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# Alias for FastAPI Depends() compatibility
get_async_session = get_session
