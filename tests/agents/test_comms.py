"""Tests for the comms agent function tools."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.comms import (
    comms_agent,
    handle_unreachable,
    schedule_reminder,
    send_communication,
)
from src.shared.types import Channel


class TestCommsAgentDefinition:
    """Comms agent is properly configured."""

    def test_has_tools(self) -> None:
        """Comms agent has function tools registered."""
        assert len(comms_agent.tools) == 3

    def test_has_instructions(self) -> None:
        """Comms agent has instructions."""
        assert comms_agent.instructions


class TestSendCommunication:
    """Communication sending."""

    async def test_sends_templated_message(self) -> None:
        """Sends a communication using a template."""
        mock_session = AsyncMock()
        with patch("src.agents.comms.log_event", return_value=MagicMock()):
            result = await send_communication(
                mock_session,
                uuid.uuid4(),
                "appointment_booked",
                Channel.SMS,
                {
                    "participant_name": "Jane",
                    "trial_name": "Study A",
                    "site_name": "OHSU",
                    "appointment_date": "2026-03-16",
                    "appointment_time": "10:00 AM",
                    "coordinator_phone": "+15035551234",
                },
            )
        assert result["sent"] is True
        assert result["channel"] is not None


class TestScheduleReminder:
    """Reminder scheduling."""

    async def test_schedules_reminder(self) -> None:
        """Schedules a reminder via Cloud Tasks."""
        mock_session = AsyncMock()
        send_at = datetime(2026, 3, 14, 10, 0, tzinfo=UTC)
        with patch("src.agents.comms.log_event", return_value=MagicMock()):
            result = await schedule_reminder(
                mock_session,
                uuid.uuid4(),
                uuid.uuid4(),
                "prep_instructions",
                Channel.SMS,
                send_at,
            )
        assert result["scheduled"] is True
        assert result["task_id"] is not None
        assert result["task_id"].startswith("task-")


class TestHandleUnreachable:
    """Unreachable workflow."""

    async def test_handles_unreachable(self) -> None:
        """Creates escalation with fallback channel."""
        mock_session = AsyncMock()
        with patch("src.agents.comms.log_event", return_value=MagicMock()):
            result = await handle_unreachable(
                mock_session,
                uuid.uuid4(),
                Channel.VOICE,
            )
        assert result["sent"] is False
        assert result["channel"] is not None
        assert result["error"] == "unreachable_on_voice"
