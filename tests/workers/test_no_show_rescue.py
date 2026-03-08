"""Tests for no-show rescue reminder handler."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from src.shared.types import AppointmentStatus
from src.workers.reminders import handle_reminder_task


class TestHandleNoShowRescue:
    """No-show rescue handler marks appointment and creates handoff."""

    async def test_marks_appointment_as_no_show(self) -> None:
        """BOOKED appointment is marked NO_SHOW with handoff ticket."""
        mock_session = AsyncMock()
        participant_id = uuid.uuid4()
        appointment_id = uuid.uuid4()

        mock_appointment = MagicMock()
        mock_appointment.status = AppointmentStatus.BOOKED
        mock_appointment.trial_id = "trial-42"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_appointment
        mock_session.execute.return_value = mock_result

        payload = {
            "participant_id": str(participant_id),
            "appointment_id": str(appointment_id),
            "template_id": "no_show_rescue",
        }

        with (
            patch(
                "src.workers.reminders._is_duplicate",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "src.workers.reminders.log_event",
                new_callable=AsyncMock,
            ),
            patch(
                "src.workers.reminders.create_handoff",
                new_callable=AsyncMock,
            ) as mock_handoff,
        ):
            result = await handle_reminder_task(mock_session, payload)

        assert result["processed"] is True
        assert result["status"] == "no_show"
        assert mock_appointment.status == AppointmentStatus.NO_SHOW
        mock_handoff.assert_called_once()

    async def test_skips_completed_appointment(self) -> None:
        """Already-completed appointment returns already_completed."""
        mock_session = AsyncMock()
        participant_id = uuid.uuid4()
        appointment_id = uuid.uuid4()

        mock_appointment = MagicMock()
        mock_appointment.status = AppointmentStatus.COMPLETED

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_appointment
        mock_session.execute.return_value = mock_result

        payload = {
            "participant_id": str(participant_id),
            "appointment_id": str(appointment_id),
            "template_id": "no_show_rescue",
        }

        with (
            patch(
                "src.workers.reminders._is_duplicate",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            result = await handle_reminder_task(mock_session, payload)

        assert result["processed"] is True
        assert result["status"] == "already_completed"

    async def test_confirmed_appointment_marked_no_show(self) -> None:
        """CONFIRMED appointment is also marked NO_SHOW."""
        mock_session = AsyncMock()
        participant_id = uuid.uuid4()
        appointment_id = uuid.uuid4()

        mock_appointment = MagicMock()
        mock_appointment.status = AppointmentStatus.CONFIRMED
        mock_appointment.trial_id = "trial-42"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_appointment
        mock_session.execute.return_value = mock_result

        payload = {
            "participant_id": str(participant_id),
            "appointment_id": str(appointment_id),
            "template_id": "no_show_rescue",
        }

        with (
            patch(
                "src.workers.reminders._is_duplicate",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "src.workers.reminders.log_event",
                new_callable=AsyncMock,
            ),
            patch(
                "src.workers.reminders.create_handoff",
                new_callable=AsyncMock,
            ) as mock_handoff,
        ):
            result = await handle_reminder_task(mock_session, payload)

        assert result["processed"] is True
        assert result["status"] == "no_show"
        assert mock_appointment.status == AppointmentStatus.NO_SHOW
        mock_handoff.assert_called_once()
