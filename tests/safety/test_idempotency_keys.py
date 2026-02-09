"""Immutable safety tests: idempotency key enforcement on events."""

import uuid
from unittest.mock import AsyncMock, MagicMock

from src.db.events import log_event


class TestIdempotencyKeys:
    """Events with duplicate idempotency keys are skipped."""

    async def test_first_event_creates_record(self) -> None:
        """First event with idempotency key is created."""
        mock_session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result_mock

        event = await log_event(
            mock_session,
            participant_id=uuid.uuid4(),
            event_type="test_event",
            idempotency_key="key-123",
            provenance="system",
        )
        assert event is not None
        mock_session.add.assert_called_once()

    async def test_duplicate_key_skips_event(self) -> None:
        """Duplicate idempotency key returns None (skip)."""
        mock_session = AsyncMock()
        existing_event = MagicMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = existing_event
        mock_session.execute.return_value = result_mock

        event = await log_event(
            mock_session,
            participant_id=uuid.uuid4(),
            event_type="test_event",
            idempotency_key="key-123",
            provenance="system",
        )
        assert event is None
        mock_session.add.assert_not_called()

    async def test_no_key_always_creates(self) -> None:
        """Event without idempotency key always creates."""
        mock_session = AsyncMock()
        event = await log_event(
            mock_session,
            participant_id=uuid.uuid4(),
            event_type="test_event",
            provenance="system",
        )
        assert event is not None
        mock_session.add.assert_called_once()
