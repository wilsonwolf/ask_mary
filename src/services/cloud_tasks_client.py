"""Cloud Tasks client — in-memory task scheduler for MVP.

Enqueues deferred jobs into an in-memory store and executes them
via a background asyncio task that POSTs to the local worker endpoint
when tasks come due. Production: replace with google-cloud-tasks calls.
"""

import asyncio
import contextlib
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from src.config.settings import get_settings

logger = logging.getLogger(__name__)

_pending_tasks: list[dict[str, object]] = []
_task_lock = asyncio.Lock()
_executor_task: asyncio.Task[None] | None = None

DEFAULT_APP_PORT = 8000
EXECUTOR_POLL_INTERVAL_SECONDS = 5


@dataclass
class TaskEnqueueResult:
    """Result of enqueuing a Cloud Tasks job.

    Attributes:
        task_id: Unique identifier for the enqueued task.
        scheduled_at: When the task is scheduled to execute.
    """

    task_id: str
    scheduled_at: str


async def enqueue_reminder(
    *,
    participant_id: uuid.UUID,
    appointment_id: uuid.UUID,
    template_id: str,
    channel: str,
    send_at: datetime,
    idempotency_key: str,
) -> TaskEnqueueResult:
    """Enqueue a reminder for future delivery.

    Stores the task in the in-memory pending list and returns
    a result with the generated task ID and schedule time.

    Args:
        participant_id: Participant UUID.
        appointment_id: Appointment UUID.
        template_id: Template identifier.
        channel: Communication channel.
        send_at: Scheduled send datetime.
        idempotency_key: Dedup key for the task.

    Returns:
        TaskEnqueueResult with task ID and schedule time.
    """
    task_id = f"task-{uuid.uuid4()}"
    task_record = _build_task_record(
        task_id=task_id,
        participant_id=participant_id,
        appointment_id=appointment_id,
        template_id=template_id,
        channel=channel,
        send_at=send_at,
        idempotency_key=idempotency_key,
    )
    async with _task_lock:
        _pending_tasks.append(task_record)
    _log_enqueue(task_id, template_id, send_at)
    return TaskEnqueueResult(
        task_id=task_id,
        scheduled_at=send_at.isoformat(),
    )


def _build_task_record(
    *,
    task_id: str,
    participant_id: uuid.UUID,
    appointment_id: uuid.UUID,
    template_id: str,
    channel: str,
    send_at: datetime,
    idempotency_key: str,
) -> dict[str, object]:
    """Build a task record dict for the in-memory store.

    Args:
        task_id: Generated task identifier.
        participant_id: Participant UUID.
        appointment_id: Appointment UUID.
        template_id: Template identifier.
        channel: Communication channel.
        send_at: Scheduled send datetime.
        idempotency_key: Dedup key for the task.

    Returns:
        Task record dict with metadata and payload.
    """
    return {
        "task_id": task_id,
        "template_id": template_id,
        "send_at": send_at.isoformat(),
        "status": "pending",
        "created_at": datetime.now(UTC).isoformat(),
        "payload": {
            "participant_id": str(participant_id),
            "appointment_id": str(appointment_id),
            "template_id": template_id,
            "channel": channel,
            "idempotency_key": idempotency_key,
        },
    }


def _log_enqueue(
    task_id: str,
    template_id: str,
    send_at: datetime,
) -> None:
    """Log task enqueue event.

    Args:
        task_id: The task identifier.
        template_id: Template identifier.
        send_at: Scheduled send datetime.
    """
    logger.info(
        "cloud_tasks_enqueued",
        extra={
            "task_id": task_id,
            "template_id": template_id,
            "send_at": send_at.isoformat(),
        },
    )


async def get_pending_tasks() -> list[dict[str, object]]:
    """Return a snapshot of all tasks in the in-memory store.

    Returns:
        List of task record dicts with status metadata.
    """
    async with _task_lock:
        return list(_pending_tasks)


def clear_pending_tasks() -> None:
    """Clear all tasks from the in-memory store.

    Used by tests to reset state between runs.
    """
    _pending_tasks.clear()


async def start_task_executor() -> None:
    """Start the background task executor loop.

    Creates an asyncio task that polls pending tasks every
    5 seconds and executes any that are due.
    """
    global _executor_task  # noqa: PLW0603
    _executor_task = asyncio.create_task(_executor_loop())
    logger.info("cloud_tasks_executor_started")


async def stop_task_executor() -> None:
    """Stop the background task executor and wait for cleanup.

    Cancels the executor task if running and awaits completion.
    """
    global _executor_task  # noqa: PLW0603
    if _executor_task is not None:
        _executor_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _executor_task
        _executor_task = None
    logger.info("cloud_tasks_executor_stopped")


async def _executor_loop() -> None:
    """Poll pending tasks and execute due ones.

    Runs indefinitely, sleeping between polls. Each due task
    is dispatched via HTTP POST to the local worker endpoint.
    """
    while True:
        await _process_due_tasks()
        await asyncio.sleep(EXECUTOR_POLL_INTERVAL_SECONDS)


async def _process_due_tasks() -> None:
    """Find and execute all tasks whose send_at has passed.

    Marks tasks as 'executing' before dispatch and updates
    status to 'completed' or 'failed' afterward.
    """
    now = datetime.now(UTC).isoformat()
    async with _task_lock:
        due_tasks = [
            task for task in _pending_tasks
            if task["status"] == "pending" and str(task["send_at"]) <= now
        ]
    for task in due_tasks:
        await _execute_task(task)


async def _execute_task(task: dict[str, object]) -> None:
    """Execute a single due task by POSTing to the worker endpoint.

    Args:
        task: Task record dict from the in-memory store.
    """
    task["status"] = "executing"
    task_id = task["task_id"]
    try:
        await _post_to_worker(task)
        task["status"] = "completed"
        logger.info("cloud_task_executed", extra={"task_id": task_id})
    except Exception:
        task["status"] = "failed"
        logger.exception("cloud_task_failed", extra={"task_id": task_id})


async def _post_to_worker(task: dict[str, object]) -> None:
    """POST task payload to the local worker reminders endpoint.

    Args:
        task: Task record dict containing the payload.
    """
    settings = get_settings()
    port = getattr(settings, "app_port", DEFAULT_APP_PORT)
    url = f"http://localhost:{port}/workers/reminders"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, json=task["payload"])
        response.raise_for_status()
