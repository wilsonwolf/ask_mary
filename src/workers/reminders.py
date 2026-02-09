"""Reminder worker — handles Cloud Tasks callbacks.

Routes deferred tasks by template_id to specialized handlers.
Cloud Tasks POSTs to the /workers/reminders endpoint with the
task payload. Each handler uses services/ and db/ only — workers
are entry points like api/ and never import from agents/.

Dependency direction: workers → services → db → shared.
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.events import log_event
from src.db.models import Appointment

logger = logging.getLogger(__name__)


async def handle_reminder_task(
    session: AsyncSession,
    payload: dict,
) -> dict:
    """Process a deferred Cloud Tasks job.

    Routes by template_id to the appropriate handler.
    Checks idempotency_key before executing to prevent
    duplicate processing from Cloud Tasks redelivery.

    Args:
        session: Active database session.
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

    if idempotency_key and await _is_duplicate(session, idempotency_key):
        return {"processed": False, "reason": "duplicate"}

    template_id = payload.get("template_id", "")
    handler = TASK_HANDLERS.get(template_id)
    if handler is None:
        return {
            "processed": False,
            "reason": f"unknown_template: {template_id}",
        }

    result = await handler(session, payload)
    return {"processed": True, **result}


async def _is_duplicate(
    session: AsyncSession,
    idempotency_key: str,
) -> bool:
    """Check if a task with this key was already processed.

    Args:
        session: Active database session.
        idempotency_key: Dedup key from Cloud Tasks payload.

    Returns:
        True if an event with this key already exists.
    """
    from src.db.models import Event

    result = await session.execute(
        select(Event).where(
            Event.idempotency_key == idempotency_key,
        )
    )
    return result.scalar_one_or_none() is not None


async def _handle_confirmation_check(
    session: AsyncSession,
    payload: dict,
) -> dict:
    """Check if a BOOKED appointment was confirmed in time.

    If still BOOKED after the 12-hour confirmation window,
    updates status to NO_RESPONSE and logs event.

    Args:
        session: Active database session.
        payload: Must contain appointment_id, participant_id.

    Returns:
        Dict with current appointment status.
    """
    appointment_id = uuid.UUID(payload["appointment_id"])
    participant_id = uuid.UUID(payload["participant_id"])

    result = await session.execute(
        select(Appointment).where(
            Appointment.appointment_id == appointment_id,
        )
    )
    appointment = result.scalar_one_or_none()
    if appointment is None:
        return {"status": "not_found"}

    if appointment.status == "booked":
        appointment.status = "no_response"
        await log_event(
            session,
            participant_id=participant_id,
            event_type="confirmation_expired",
            appointment_id=appointment_id,
            idempotency_key=payload.get("idempotency_key"),
            provenance="system",
            channel="system",
        )
        return {"status": "no_response"}

    return {"status": appointment.status}


async def _handle_slot_release(
    session: AsyncSession,
    payload: dict,
) -> dict:
    """Release a held slot that was never booked.

    Updates appointment status from HELD to RELEASED.

    Args:
        session: Active database session.
        payload: Must contain appointment_id, participant_id.

    Returns:
        Dict with release result.
    """
    appointment_id = uuid.UUID(payload["appointment_id"])
    participant_id = uuid.UUID(payload["participant_id"])

    result = await session.execute(
        select(Appointment).where(
            Appointment.appointment_id == appointment_id,
        )
    )
    appointment = result.scalar_one_or_none()
    if appointment is None:
        return {"released": False, "reason": "not_found"}

    if appointment.status == "held":
        appointment.status = "released"
        await log_event(
            session,
            participant_id=participant_id,
            event_type="slot_released",
            appointment_id=appointment_id,
            idempotency_key=payload.get("idempotency_key"),
            provenance="system",
            channel="system",
        )
        return {"released": True}

    return {"released": False, "reason": f"status_{appointment.status}"}


async def _handle_reminder(
    session: AsyncSession,
    payload: dict,
) -> dict:
    """Render and send a reminder via the appropriate channel.

    Uses shared/comms.py for template rendering and logs the
    send event. Actual delivery is stubbed for MVP.

    Args:
        session: Active database session.
        payload: Must contain participant_id, template_id, channel.

    Returns:
        Dict with send result.
    """
    from src.shared.comms import render_template

    participant_id = uuid.UUID(payload["participant_id"])
    template_id = payload["template_id"]
    channel = payload.get("channel", "sms")

    try:
        rendered = render_template(template_id)
    except FileNotFoundError:
        return {"sent": False, "reason": "template_not_found"}

    logger.info(
        "reminder_rendered",
        extra={
            "template_id": template_id,
            "channel": channel,
            "length": len(rendered),
        },
    )

    await log_event(
        session,
        participant_id=participant_id,
        event_type="reminder_sent",
        idempotency_key=payload.get("idempotency_key"),
        payload={"template_id": template_id, "channel": channel},
        provenance="system",
        channel=channel,
    )

    return {"sent": True, "channel": channel}


TASK_HANDLERS = {
    "confirmation_check": _handle_confirmation_check,
    "slot_release": _handle_slot_release,
    "appointment_reminder": _handle_reminder,
    "visit_reminder": _handle_reminder,
}
