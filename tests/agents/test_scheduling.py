"""Tests for the scheduling agent function tools."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.scheduling import (
    book_appointment,
    check_geo_eligibility,
    find_available_slots,
    hold_slot,
    release_expired_slot,
    scheduling_agent,
    verify_teach_back,
)


class TestSchedulingAgentDefinition:
    """Scheduling agent is properly configured."""

    def test_has_tools(self) -> None:
        """Scheduling agent has function tools registered."""
        assert len(scheduling_agent.tools) == 6

    def test_has_instructions(self) -> None:
        """Scheduling agent has instructions."""
        assert scheduling_agent.instructions


class TestCheckGeoEligibility:
    """Geo/distance gate check."""

    async def test_eligible_within_range(self) -> None:
        """Participant within max distance is eligible."""
        mock_session = AsyncMock()
        participant = MagicMock()
        participant.distance_to_site_km = 30.0
        trial = MagicMock()
        trial.max_distance_km = 80.0

        with (
            patch("src.agents.scheduling.get_participant_by_id", return_value=participant),
            patch("src.agents.scheduling.get_trial", return_value=trial),
        ):
            result = await check_geo_eligibility(mock_session, uuid.uuid4(), "trial-1")
        assert result["eligible"] is True

    async def test_ineligible_outside_range(self) -> None:
        """Participant beyond max distance is ineligible."""
        mock_session = AsyncMock()
        participant = MagicMock()
        participant.distance_to_site_km = 100.0
        trial = MagicMock()
        trial.max_distance_km = 80.0

        with (
            patch("src.agents.scheduling.get_participant_by_id", return_value=participant),
            patch("src.agents.scheduling.get_trial", return_value=trial),
        ):
            result = await check_geo_eligibility(mock_session, uuid.uuid4(), "trial-1")
        assert result["eligible"] is False

    async def test_eligible_when_distance_unknown(self) -> None:
        """Participant with no distance defaults to eligible."""
        mock_session = AsyncMock()
        participant = MagicMock()
        participant.distance_to_site_km = None
        trial = MagicMock()
        trial.max_distance_km = 80.0

        with (
            patch("src.agents.scheduling.get_participant_by_id", return_value=participant),
            patch("src.agents.scheduling.get_trial", return_value=trial),
        ):
            result = await check_geo_eligibility(mock_session, uuid.uuid4(), "trial-1")
        assert result["eligible"] is True


class TestFindAvailableSlots:
    """Slot availability query."""

    async def test_returns_slots(self) -> None:
        """Returns a list of available slot datetimes."""
        mock_session = AsyncMock()
        trial = MagicMock()
        trial.operating_hours = {
            "monday": {"open": "08:00", "close": "17:00"},
        }
        with patch("src.agents.scheduling.get_trial", return_value=trial):
            result = await find_available_slots(mock_session, "trial-1", ["2026-03-16"])
        assert "slots" in result
        assert isinstance(result["slots"], list)


class TestHoldSlot:
    """Slot hold with SELECT FOR UPDATE."""

    async def test_holds_slot(self) -> None:
        """Returns hold confirmation with expiry time."""
        mock_session = AsyncMock()
        slot_time = datetime.now(UTC) + timedelta(days=7)
        mock_appointment = MagicMock()
        mock_appointment.appointment_id = uuid.uuid4()

        # No conflict (SELECT FOR UPDATE returns None)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result_mock

        with patch(
            "src.agents.scheduling.create_appointment",
            return_value=mock_appointment,
        ):
            result = await hold_slot(
                mock_session, uuid.uuid4(), "trial-1", slot_time,
            )
        assert result["held"] is True
        assert "expires_at" in result
        assert "appointment_id" in result

    async def test_rejects_taken_slot(self) -> None:
        """Returns held=False when slot is already taken."""
        mock_session = AsyncMock()
        slot_time = datetime.now(UTC) + timedelta(days=7)

        # Conflict exists
        existing = MagicMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = existing
        mock_session.execute.return_value = result_mock

        result = await hold_slot(
            mock_session, uuid.uuid4(), "trial-1", slot_time,
        )
        assert result["held"] is False
        assert result["reason"] == "slot_taken"


class TestBookAppointment:
    """Appointment booking."""

    async def test_books_with_confirmation_window(self) -> None:
        """Books appointment with 12-hour confirmation window."""
        mock_session = AsyncMock()
        slot_time = datetime.now(UTC) + timedelta(days=7)
        mock_appointment = MagicMock()
        mock_appointment.appointment_id = uuid.uuid4()

        with patch(
            "src.agents.scheduling.create_appointment",
            return_value=mock_appointment,
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


class TestVerifyTeachBack:
    """Teach-back verification."""

    async def test_passes_with_correct_answers(self) -> None:
        """Teach-back passes when all answers match."""
        mock_session = AsyncMock()
        appointment = MagicMock()
        appointment.scheduled_at = datetime(2026, 3, 16, 10, 0, tzinfo=UTC)
        appointment.site_name = "OHSU"
        appointment.site_address = "3181 SW Sam Jackson"
        appointment.teach_back_attempts = 0

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = appointment
        mock_session.execute.return_value = result_mock

        result = await verify_teach_back(
            mock_session,
            uuid.uuid4(),
            uuid.uuid4(),
            "March 16",
            "10 AM",
            "OHSU",
        )
        assert result["passed"] is True

    async def test_fails_with_wrong_location(self) -> None:
        """Teach-back fails when location answer is wrong."""
        mock_session = AsyncMock()
        appointment = MagicMock()
        appointment.scheduled_at = datetime(2026, 3, 16, 10, 0, tzinfo=UTC)
        appointment.site_name = "OHSU"
        appointment.site_address = "3181 SW Sam Jackson"
        appointment.teach_back_attempts = 0

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = appointment
        mock_session.execute.return_value = result_mock

        result = await verify_teach_back(
            mock_session,
            uuid.uuid4(),
            uuid.uuid4(),
            "March 16",
            "10 AM",
            "wrong place",
        )
        assert result["passed"] is False


class TestReleaseExpiredSlot:
    """Slot expiry and release."""

    async def test_releases_expired_slot(self) -> None:
        """Expired slot is marked as released."""
        mock_session = AsyncMock()
        appointment = MagicMock()
        appointment.status = "booked"
        appointment.slot_held_until = datetime.now(UTC) - timedelta(hours=1)

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = appointment
        mock_session.execute.return_value = result_mock

        result = await release_expired_slot(mock_session, uuid.uuid4())
        assert result["released"] is True
