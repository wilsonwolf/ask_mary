"""Cloud Tasks client — enqueues deferred jobs.

MVP stub: logs the task payload and returns a mock task ID.
Production: replace with google-cloud-tasks client calls.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


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
    """Enqueue a reminder for future delivery via Cloud Tasks.

    MVP: stub that logs and returns a mock task ID.
    Production: POST to Cloud Tasks queue.

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
    logger.info(
        "cloud_tasks_enqueue_stub",
        extra={
            "task_id": task_id,
            "participant_id": str(participant_id),
            "appointment_id": str(appointment_id),
            "template_id": template_id,
            "channel": channel,
            "send_at": send_at.isoformat(),
            "idempotency_key": idempotency_key,
        },
    )
    return TaskEnqueueResult(
        task_id=task_id,
        scheduled_at=send_at.isoformat(),
    )
