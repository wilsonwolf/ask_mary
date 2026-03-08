"""Tests for comms cadence scheduling after appointment booking."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from src.api.webhooks import _schedule_comms_cadence


class TestScheduleCommsCadence:
    """Comms cadence scheduling enqueues prep, confirm, day-of reminders."""

    async def test_enqueues_three_reminders(self) -> None:
        """All three reminders enqueued for a future appointment."""
        mock_session = AsyncMock()
        participant_id = uuid.uuid4()
        appointment_id = uuid.uuid4()
        scheduled_at = datetime.now(UTC) + timedelta(hours=72)

        mock_result = AsyncMock()
        mock_result.scheduled = True
        mock_result.task_id = "task-123"

        with patch(
            "src.api.webhooks.schedule_reminder",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_schedule:
            await _schedule_comms_cadence(
                mock_session,
                participant_id,
                appointment_id,
                scheduled_at,
            )

        assert mock_schedule.call_count == 3
        template_ids = [
            call.kwargs["template_id"]
            for call in mock_schedule.call_args_list
        ]
        assert "prep_instructions" in template_ids
        assert "confirmation_prompt" in template_ids
        assert "day_of_checkin" in template_ids

    async def test_skips_past_due_reminders(self) -> None:
        """Reminders whose send_at is in the past are skipped."""
        mock_session = AsyncMock()
        participant_id = uuid.uuid4()
        appointment_id = uuid.uuid4()
        scheduled_at = datetime.now(UTC) + timedelta(hours=3)

        mock_result = AsyncMock()
        mock_result.scheduled = True
        mock_result.task_id = "task-456"

        with patch(
            "src.api.webhooks.schedule_reminder",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_schedule:
            await _schedule_comms_cadence(
                mock_session,
                participant_id,
                appointment_id,
                scheduled_at,
            )

        assert mock_schedule.call_count == 1
        template_id = mock_schedule.call_args.kwargs["template_id"]
        assert template_id == "day_of_checkin"

    async def test_one_failure_does_not_block_others(self) -> None:
        """A failure scheduling one reminder does not prevent others."""
        mock_session = AsyncMock()
        participant_id = uuid.uuid4()
        appointment_id = uuid.uuid4()
        scheduled_at = datetime.now(UTC) + timedelta(hours=72)

        call_count = 0

        async def _side_effect(**kwargs: object) -> AsyncMock:
            nonlocal call_count
            call_count += 1
            if kwargs.get("template_id") == "prep_instructions":
                raise RuntimeError("Cloud Tasks unavailable")
            result = AsyncMock()
            result.scheduled = True
            result.task_id = f"task-{call_count}"
            return result

        with patch(
            "src.api.webhooks.schedule_reminder",
            new_callable=AsyncMock,
            side_effect=_side_effect,
        ) as mock_schedule:
            await _schedule_comms_cadence(
                mock_session,
                participant_id,
                appointment_id,
                scheduled_at,
            )

        assert mock_schedule.call_count == 3
