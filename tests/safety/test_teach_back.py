"""Immutable safety tests: teach-back handoff after 2 failures."""

import uuid
from unittest.mock import AsyncMock, MagicMock

from src.agents.scheduling import verify_teach_back


class TestTeachBack:
    """Teach-back verification with handoff on repeated failure."""

    async def test_passes_with_correct_answers(self) -> None:
        """Teach-back passes when location matches site name."""
        mock_session = AsyncMock()
        appointment = MagicMock()
        appointment.site_name = "OHSU"
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
        """Teach-back fails when location does not match."""
        mock_session = AsyncMock()
        appointment = MagicMock()
        appointment.site_name = "OHSU"
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

    async def test_handoff_required_after_two_failures(self) -> None:
        """After 2 failures, handoff_required is set to True."""
        mock_session = AsyncMock()
        appointment = MagicMock()
        appointment.site_name = "OHSU"
        appointment.teach_back_attempts = 1
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
        assert result["handoff_required"] is True
        assert result["attempts"] == 2
