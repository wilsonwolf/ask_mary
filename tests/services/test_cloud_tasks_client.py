"""Tests for the Cloud Tasks client stub."""

import uuid
from datetime import UTC, datetime

from src.services.cloud_tasks_client import (
    TaskEnqueueResult,
    enqueue_reminder,
)


class TestEnqueueReminder:
    """Cloud Tasks enqueue stub."""

    async def test_returns_task_result(self) -> None:
        """Enqueue returns a task ID and schedule time."""
        send_at = datetime(2026, 3, 14, 10, 0, tzinfo=UTC)
        result = await enqueue_reminder(
            participant_id=uuid.uuid4(),
            appointment_id=uuid.uuid4(),
            template_id="prep_instructions",
            channel="sms",
            send_at=send_at,
            idempotency_key="reminder-test-123",
        )
        assert isinstance(result, TaskEnqueueResult)
        assert result.task_id.startswith("task-")
        assert result.scheduled_at == send_at.isoformat()
