"""Immutable safety tests: 12-hour confirmation window enforcement."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.scheduling import (
    CONFIRMATION_WINDOW_HOURS,
    book_appointment,
    release_expired_slot,
)


class TestConfirmationWindow:
    """Booking creates 12-hour confirmation window; expiry releases slot."""

    async def test_booking_sets_confirmation_deadline(self) -> None:
        """Booking sets confirmation_due_at to 12 hours from now."""
        mock_session = AsyncMock()
        slot_time = datetime.now(UTC) + timedelta(days=7)
        held = MagicMock()
        held.appointment_id = uuid.uuid4()
        held.status = "held"
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = held
        mock_session.execute.return_value = result_mock
        with patch(
            "src.agents.scheduling.log_event",
            return_value=MagicMock(),
        ):
            result = await book_appointment(
                mock_session,
                uuid.uuid4(),
                "trial-1",
                slot_time,
                "screening",
            )
        assert result["booked"] is True
        assert "confirmation_due_at" in result
        assert CONFIRMATION_WINDOW_HOURS == 12

    async def test_expired_slot_is_released(self) -> None:
        """Expired slot is marked as expired_unconfirmed."""
        mock_session = AsyncMock()
        appointment = MagicMock()
        appointment.status = "booked"
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = appointment
        mock_session.execute.return_value = result_mock
        result = await release_expired_slot(
            mock_session,
            uuid.uuid4(),
        )
        assert result["released"] is True
        assert appointment.status == "expired_unconfirmed"

    async def test_booking_rejects_slot_conflict(self) -> None:
        """Booking rejects when another participant holds slot."""
        mock_session = AsyncMock()
        slot_time = datetime.now(UTC) + timedelta(days=7)
        no_held = MagicMock()
        no_held.scalar_one_or_none.return_value = None
        has_conflict = MagicMock()
        has_conflict.scalar_one_or_none.return_value = MagicMock()
        mock_session.execute.side_effect = [no_held, has_conflict]
        result = await book_appointment(
            mock_session,
            uuid.uuid4(),
            "trial-1",
            slot_time,
            "screening",
        )
        assert result["booked"] is False
        assert result["reason"] == "slot_taken"
