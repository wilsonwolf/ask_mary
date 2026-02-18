"""Integration tests for append-only event logging."""

import uuid
from unittest.mock import AsyncMock, MagicMock

from src.db.events import log_event


class TestEventsAppendOnly:
    """Events are append-only with idempotency enforcement."""

    async def test_log_event_creates_record(self) -> None:
        """Log event creates and flushes a new event."""
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        event = await log_event(
            mock_session,
            participant_id=uuid.uuid4(),
            event_type="test_event",
            payload={"test": True},
            provenance="system",
        )
        assert event is not None
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()

    async def test_idempotency_dedup(self) -> None:
        """Duplicate idempotency key skips event creation."""
        mock_session = AsyncMock()
        existing = MagicMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = existing
        mock_session.execute.return_value = result_mock

        event = await log_event(
            mock_session,
            participant_id=uuid.uuid4(),
            event_type="test_event",
            idempotency_key="dup-key",
            provenance="system",
        )
        assert event is None

    async def test_provenance_recorded(self) -> None:
        """Event records provenance field."""
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        event = await log_event(
            mock_session,
            participant_id=uuid.uuid4(),
            event_type="consent_captured",
            provenance="patient_stated",
        )
        assert event is not None
        assert event.provenance == "patient_stated"
