"""Tests for the transport agent function tools."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.transport import (
    book_transport,
    check_ride_status,
    confirm_pickup_address,
    transport_agent,
)


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


class TestCheckRideStatus:
    """Ride status check."""

    async def test_returns_status(self) -> None:
        """Returns current ride status."""
        mock_session = AsyncMock()
        ride = MagicMock()
        ride.status = "confirmed"
        ride.uber_ride_id = "mock-ride-123"

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = ride
        mock_session.execute.return_value = result_mock

        result = await check_ride_status(mock_session, uuid.uuid4())
        assert result["status"] == "confirmed"
