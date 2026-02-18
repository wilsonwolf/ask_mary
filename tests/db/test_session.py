"""Tests for the async database session dependency."""

from unittest.mock import AsyncMock, MagicMock, patch

from src.db.session import get_session


class TestGetSession:
    """Session dependency yields and commits."""

    async def test_commits_on_success(self) -> None:
        """Session is committed after successful use."""
        mock_session = AsyncMock()

        mock_factory = MagicMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_session
        mock_ctx.__aexit__.return_value = False
        mock_factory.return_value = mock_ctx

        with patch(
            "src.db.session._get_session_factory",
            return_value=mock_factory,
        ):
            gen = get_session()
            session = await gen.__anext__()
            assert session is mock_session
            import contextlib

            with contextlib.suppress(StopAsyncIteration):
                await gen.__anext__()

        mock_session.commit.assert_awaited_once()
