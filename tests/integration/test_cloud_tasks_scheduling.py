"""Integration tests for Cloud Tasks scheduling."""

import uuid
from datetime import UTC, datetime, timedelta

from src.services.cloud_tasks_client import enqueue_reminder


class TestCloudTasksScheduling:
    """Cloud Tasks job enqueuing."""

    async def test_enqueue_reminder_returns_task_id(self) -> None:
        """Enqueued reminder returns a task ID starting with 'task-'."""
        result = await enqueue_reminder(
            participant_id=uuid.uuid4(),
            appointment_id=uuid.uuid4(),
            template_id="confirmation_check",
            channel="sms",
            send_at=datetime.now(UTC) + timedelta(hours=11),
            idempotency_key="test-key-123",
        )
        assert result.task_id.startswith("task-")
        assert result.scheduled_at

    async def test_task_result_structure(self) -> None:
        """Task result has expected fields."""
        result = await enqueue_reminder(
            participant_id=uuid.uuid4(),
            appointment_id=uuid.uuid4(),
            template_id="reminder_24h",
            channel="voice",
            send_at=datetime.now(UTC) + timedelta(hours=24),
            idempotency_key="test-key-456",
        )
        assert hasattr(result, "task_id")
        assert hasattr(result, "scheduled_at")
