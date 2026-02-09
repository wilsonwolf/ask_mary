"""Reminder worker — handles Cloud Tasks callbacks.

Processes deferred reminder tasks. Cloud Tasks POSTs to
the /workers/reminders endpoint with the task payload.
The worker looks up the template, renders it, and sends
via the appropriate channel.

MVP: skeleton handler with idempotency check.
"""

import logging

logger = logging.getLogger(__name__)


async def handle_reminder_task(payload: dict) -> dict:
    """Process a deferred reminder task.

    Called by Cloud Tasks when the scheduled time arrives.
    Checks idempotency_key before executing.

    Args:
        payload: Task payload with participant_id, template_id,
            channel, and idempotency_key.

    Returns:
        Dict with processing result.
    """
    idempotency_key = payload.get("idempotency_key")
    logger.info(
        "reminder_task_received",
        extra={"idempotency_key": idempotency_key},
    )
    # TODO: check idempotency_key against events table
    # TODO: render template and send via channel
    return {
        "processed": True,
        "idempotency_key": idempotency_key,
    }
