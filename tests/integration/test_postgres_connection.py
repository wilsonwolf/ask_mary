"""Integration tests for Postgres session management."""

from unittest.mock import AsyncMock, MagicMock, patch

from src.db.session import get_session


class TestPostgresConnection:
    """Database session lifecycle."""

    async def test_session_yields(self) -> None:
        """get_session yields an async session object."""
        mock_session = AsyncMock()
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_context.__aexit__.return_value = False
        mock_factory = MagicMock(return_value=mock_context)

        with patch("src.db.session._get_session_factory", return_value=mock_factory):
            async for session in get_session():
                assert session is mock_session
                break

    async def test_session_commits_on_success(self) -> None:
        """Session commits when no exception occurs."""
        mock_session = AsyncMock()
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_context.__aexit__.return_value = False
        mock_factory = MagicMock(return_value=mock_context)

        with patch("src.db.session._get_session_factory", return_value=mock_factory):
            async for _session in get_session():
                pass
            mock_session.commit.assert_awaited_once()
