"""Tests for the transport agent function tools."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.transport import (
    _schedule_ride_reconfirmation,
    book_transport,
    check_ride_status,
    confirm_pickup_address,
    transport_agent,
)
from src.shared.types import RideStatus


class TestTransportAgentDefinition:
    """Transport agent is properly configured."""

    def test_has_tools(self) -> None:
        """Transport agent has function tools registered."""
        assert len(transport_agent.tools) == 3

    def test_has_instructions(self) -> None:
        """Transport agent has instructions."""
        assert transport_agent.instructions


class TestConfirmPickupAddress:
    """Pickup address confirmation."""

    async def test_confirms_address(self) -> None:
        """Confirms pickup address against participant record."""
        mock_session = AsyncMock()
        participant = MagicMock()
        participant.address_street = "123 Main St"
        participant.address_city = "Portland"
        participant.address_state = "OR"
        participant.address_zip = "97201"
        with patch(
            "src.agents.transport.get_participant_by_id",
            return_value=participant,
        ):
            result = await confirm_pickup_address(mock_session, uuid.uuid4(), "123 Main St")
        assert result["confirmed"] is True


class TestBookTransport:
    """Transport booking."""

    async def test_books_ride(self) -> None:
        """Books a ride and creates a ride record."""
        mock_session = AsyncMock()
        mock_ride = MagicMock()
        mock_ride.ride_id = uuid.uuid4()
        appointment = MagicMock()
        appointment.site_address = "456 Oak Ave"
        appointment.scheduled_at = datetime(2026, 3, 16, 10, 0, tzinfo=UTC)

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = appointment
        mock_session.execute.return_value = result_mock

        with patch("src.agents.transport.create_ride", return_value=mock_ride):
            result = await book_transport(
                mock_session,
                uuid.uuid4(),
                uuid.uuid4(),
                "123 Main St, Portland OR 97201",
            )
        assert result["booked"] is True
        assert result["pickup_address"] == "123 Main St, Portland OR 97201"
        assert result["dropoff_address"] == "456 Oak Ave"
        assert "scheduled_pickup_at" in result

    async def test_returns_error_when_appointment_not_found(self) -> None:
        """Returns error when appointment does not exist."""
        mock_session = AsyncMock()

        with patch("src.agents.transport.get_appointment", return_value=None):
            result = await book_transport(
                mock_session,
                uuid.uuid4(),
                uuid.uuid4(),
                "123 Main St, Portland OR 97201",
            )
        assert result["booked"] is False
        assert result["error"] == "appointment_not_found"


class TestCheckRideStatus:
    """Ride status check."""

    async def test_returns_status(self) -> None:
        """Returns current ride status."""
        mock_session = AsyncMock()
        ride = MagicMock()
        ride.status = RideStatus.CONFIRMED
        ride.uber_ride_id = "mock-ride-123"

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = ride
        mock_session.execute.return_value = result_mock

        result = await check_ride_status(mock_session, uuid.uuid4())
        assert result["booked"] is True


class TestScheduleRideReconfirmation:
    """Ride reconfirmation task scheduling."""

    async def test_enqueues_two_tasks(self) -> None:
        """Schedules both T-24h and T-2h reconfirmation tasks."""
        ride_id = uuid.uuid4()
        participant_id = uuid.uuid4()
        appointment_id = uuid.uuid4()
        pickup_at = datetime.now(UTC) + timedelta(hours=48)
        mock_enqueue = AsyncMock()

        with patch(
            "src.agents.transport.enqueue_reminder",
            mock_enqueue,
        ):
            await _schedule_ride_reconfirmation(
                participant_id, appointment_id, ride_id, pickup_at,
            )

        assert mock_enqueue.await_count == 2
        calls = mock_enqueue.call_args_list
        assert calls[0].kwargs["template_id"] == "transport_reconfirm_24h"
        assert calls[1].kwargs["template_id"] == "transport_reconfirm_2h"

    async def test_correct_timing(self) -> None:
        """T-24h and T-2h send_at values match expected offsets."""
        ride_id = uuid.uuid4()
        pickup_at = datetime.now(UTC) + timedelta(hours=48)
        mock_enqueue = AsyncMock()

        with patch(
            "src.agents.transport.enqueue_reminder",
            mock_enqueue,
        ):
            await _schedule_ride_reconfirmation(
                uuid.uuid4(), uuid.uuid4(), ride_id, pickup_at,
            )

        calls = mock_enqueue.call_args_list
        expected_24h = pickup_at - timedelta(hours=24)
        expected_2h = pickup_at - timedelta(hours=2)
        assert calls[0].kwargs["send_at"] == expected_24h
        assert calls[1].kwargs["send_at"] == expected_2h

    async def test_skips_past_due_reconfirmations(self) -> None:
        """Does not enqueue tasks when send_at is in the past."""
        ride_id = uuid.uuid4()
        pickup_at = datetime.now(UTC) + timedelta(hours=1)
        mock_enqueue = AsyncMock()

        with patch(
            "src.agents.transport.enqueue_reminder",
            mock_enqueue,
        ):
            await _schedule_ride_reconfirmation(
                uuid.uuid4(), uuid.uuid4(), ride_id, pickup_at,
            )

        assert mock_enqueue.await_count == 0

    async def test_idempotency_keys_contain_ride_id(self) -> None:
        """Idempotency keys include the ride_id for uniqueness."""
        ride_id = uuid.uuid4()
        pickup_at = datetime.now(UTC) + timedelta(hours=48)
        mock_enqueue = AsyncMock()

        with patch(
            "src.agents.transport.enqueue_reminder",
            mock_enqueue,
        ):
            await _schedule_ride_reconfirmation(
                uuid.uuid4(), uuid.uuid4(), ride_id, pickup_at,
            )

        calls = mock_enqueue.call_args_list
        key_24h = calls[0].kwargs["idempotency_key"]
        key_2h = calls[1].kwargs["idempotency_key"]
        assert f"transport-reconfirm-24h-{ride_id}" == key_24h
        assert f"transport-reconfirm-2h-{ride_id}" == key_2h

    async def test_scheduling_failure_does_not_raise(self) -> None:
        """Enqueue failure is caught without propagating."""
        ride_id = uuid.uuid4()
        pickup_at = datetime.now(UTC) + timedelta(hours=48)
        mock_enqueue = AsyncMock(side_effect=RuntimeError("queue down"))

        with patch(
            "src.agents.transport.enqueue_reminder",
            mock_enqueue,
        ):
            await _schedule_ride_reconfirmation(
                uuid.uuid4(), uuid.uuid4(), ride_id, pickup_at,
            )

    async def test_book_transport_calls_reconfirmation(self) -> None:
        """book_transport schedules reconfirmation after ride creation."""
        mock_session = AsyncMock()
        mock_ride = MagicMock()
        mock_ride.ride_id = uuid.uuid4()
        appointment = MagicMock()
        appointment.site_address = "456 Oak Ave"
        appointment.scheduled_at = datetime(2026, 3, 16, 10, 0, tzinfo=UTC)

        with (
            patch("src.agents.transport.get_appointment", return_value=appointment),
            patch("src.agents.transport.create_ride", return_value=mock_ride),
            patch(
                "src.agents.transport._schedule_ride_reconfirmation",
                new_callable=AsyncMock,
            ) as mock_schedule,
        ):
            await book_transport(
                mock_session,
                uuid.uuid4(),
                uuid.uuid4(),
                "123 Main St",
            )

        mock_schedule.assert_awaited_once()
