"""Tests for the Cloud Tasks client — in-memory task scheduler."""

import uuid
from datetime import UTC, datetime

import pytest

from src.services.cloud_tasks_client import (
    TaskEnqueueResult,
    clear_pending_tasks,
    enqueue_reminder,
    get_pending_tasks,
)


@pytest.fixture(autouse=True)
def _clean_task_store() -> None:
    """Clear the in-memory task store before each test."""
    clear_pending_tasks()


class TestEnqueueReminder:
    """Cloud Tasks enqueue — stores tasks in memory."""

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


class TestEnqueueStoresTask:
    """Verify enqueue persists tasks in the in-memory store."""

    async def test_enqueue_stores_task(self) -> None:
        """Enqueuing a reminder adds it to pending tasks."""
        send_at = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)
        await enqueue_reminder(
            participant_id=uuid.uuid4(),
            appointment_id=uuid.uuid4(),
            template_id="confirmation_check",
            channel="sms",
            send_at=send_at,
            idempotency_key="store-test-001",
        )
        pending = await get_pending_tasks()
        assert len(pending) == 1
        assert pending[0]["template_id"] == "confirmation_check"
        assert pending[0]["status"] == "pending"


class TestTaskHasRequiredFields:
    """Verify stored tasks contain all required metadata."""

    async def test_task_has_required_fields(self) -> None:
        """Stored task includes task_id, template_id, send_at, payload."""
        send_at = datetime(2026, 5, 10, 14, 30, tzinfo=UTC)
        participant_id = uuid.uuid4()
        appointment_id = uuid.uuid4()
        await enqueue_reminder(
            participant_id=participant_id,
            appointment_id=appointment_id,
            template_id="slot_expiry",
            channel="system",
            send_at=send_at,
            idempotency_key="fields-test-002",
        )
        pending = await get_pending_tasks()
        task = pending[0]
        assert "task_id" in task
        assert task["task_id"].startswith("task-")
        assert task["template_id"] == "slot_expiry"
        assert task["send_at"] == send_at.isoformat()
        assert "payload" in task
        payload = task["payload"]
        assert payload["participant_id"] == str(participant_id)
        assert payload["appointment_id"] == str(appointment_id)


class TestGetPendingTasksReturnsList:
    """Verify the accessor returns a list."""

    async def test_get_pending_tasks_returns_list(self) -> None:
        """get_pending_tasks returns a list even when empty."""
        pending = await get_pending_tasks()
        assert isinstance(pending, list)
        assert len(pending) == 0

    async def test_multiple_tasks_returned(self) -> None:
        """Multiple enqueued tasks all appear in pending list."""
        send_at = datetime(2026, 6, 1, 8, 0, tzinfo=UTC)
        for i in range(3):
            await enqueue_reminder(
                participant_id=uuid.uuid4(),
                appointment_id=uuid.uuid4(),
                template_id=f"reminder_{i}",
                channel="sms",
                send_at=send_at,
                idempotency_key=f"multi-test-{i}",
            )
        pending = await get_pending_tasks()
        assert len(pending) == 3
