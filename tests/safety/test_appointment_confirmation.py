"""Immutable safety tests: appointment booking confirmation."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.scheduling import book_appointment


class TestAppointmentConfirmation:
    """Booking creates confirmation window and logs event."""

    async def test_confirms_held_appointment(self) -> None:
        """Held appointment transitions to booked status."""
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
        assert held.status == "booked"

    async def test_books_new_when_no_held_slot(self) -> None:
        """Creates new appointment when no held slot exists."""
        mock_session = AsyncMock()
        slot_time = datetime.now(UTC) + timedelta(days=7)
        mock_appointment = MagicMock()
        mock_appointment.appointment_id = uuid.uuid4()
        no_result = MagicMock()
        no_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = no_result
        with (
            patch(
                "src.agents.scheduling.create_appointment",
                return_value=mock_appointment,
            ),
            patch(
                "src.agents.scheduling.log_event",
                return_value=MagicMock(),
            ),
        ):
            result = await book_appointment(
                mock_session,
                uuid.uuid4(),
                "trial-1",
                slot_time,
                "screening",
            )
        assert result["booked"] is True

    async def test_booking_logs_event(self) -> None:
        """Booking logs an appointment_booked event."""
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
        ) as log_mock:
            await book_appointment(
                mock_session,
                uuid.uuid4(),
                "trial-1",
                slot_time,
                "screening",
            )
        log_mock.assert_called_once()
        call_kwargs = log_mock.call_args
        assert call_kwargs.kwargs["event_type"] == "appointment_booked"
