"""Immutable safety tests: transport pickup address verification."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.transport import book_transport, confirm_pickup_address


class TestUberPickupVerification:
    """Pickup address verification before transport booking."""

    async def test_confirms_matching_address(self) -> None:
        """Address matching record on file is confirmed."""
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
            result = await confirm_pickup_address(
                mock_session,
                uuid.uuid4(),
                "123 Main St, Portland, OR 97201",
            )
        assert result["confirmed"] is True
        assert result["is_match"] is True

    async def test_flags_mismatched_address(self) -> None:
        """Non-matching address is flagged as mismatch."""
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
            result = await confirm_pickup_address(
                mock_session,
                uuid.uuid4(),
                "999 Other Ave, Seattle, WA 98101",
            )
        assert result["confirmed"] is True
        assert result["is_match"] is False

    async def test_books_transport_for_appointment(self) -> None:
        """Transport booking creates a ride record."""
        mock_session = AsyncMock()
        appointment = MagicMock()
        appointment.scheduled_at = datetime.now(UTC) + timedelta(days=7)
        appointment.site_address = "3181 SW Sam Jackson"
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = appointment
        mock_session.execute.return_value = result_mock
        mock_ride = MagicMock()
        mock_ride.ride_id = uuid.uuid4()
        with patch(
            "src.agents.transport.create_ride",
            return_value=mock_ride,
        ):
            result = await book_transport(
                mock_session,
                uuid.uuid4(),
                uuid.uuid4(),
                "123 Main St, Portland, OR 97201",
            )
        assert result["booked"] is True
        assert "ride_id" in result
