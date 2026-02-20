"""Reminder worker — handles Cloud Tasks callbacks.

Routes deferred tasks by template_id to specialized handlers.
Cloud Tasks POSTs to the /workers/reminders endpoint with the
task payload. Each handler uses services/ and db/ only — workers
are entry points like api/ and never import from agents/.

Dependency direction: workers → services → db → shared.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.events import log_event
from src.db.models import Appointment
from src.db.postgres import create_handoff, get_ride
from src.shared.types import (
    AppointmentStatus,
    Channel,
    HandoffReason,
    HandoffSeverity,
    Provenance,
    RideStatus,
)

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

    if appointment.status == AppointmentStatus.BOOKED:
        appointment.status = AppointmentStatus.EXPIRED_UNCONFIRMED
        await log_event(
            session,
            participant_id=participant_id,
            event_type="confirmation_expired",
            appointment_id=appointment_id,
            idempotency_key=payload.get("idempotency_key"),
            provenance=Provenance.SYSTEM,
            channel=Channel.SYSTEM,
        )
        await _release_and_follow_up(
            participant_id, appointment_id,
        )
        return {"status": AppointmentStatus.EXPIRED_UNCONFIRMED}

    return {"status": appointment.status}


async def _release_and_follow_up(
    participant_id: uuid.UUID,
    appointment_id: uuid.UUID,
) -> None:
    """Release slot and schedule follow-up after confirmation expiry.

    Args:
        participant_id: Participant UUID.
        appointment_id: Appointment UUID.
    """
    from src.services.cloud_tasks_client import enqueue_reminder

    now = datetime.now(UTC)
    try:
        await enqueue_reminder(
            participant_id=participant_id,
            appointment_id=appointment_id,
            template_id="slot_release",
            channel=Channel.SYSTEM,
            send_at=now,
            idempotency_key=f"expire-release-{appointment_id}",
        )
    except Exception:
        logger.debug("slot_release_enqueue_failed")

    try:
        await enqueue_reminder(
            participant_id=participant_id,
            appointment_id=appointment_id,
            template_id="appointment_reminder",
            channel=Channel.SMS,
            send_at=now + timedelta(hours=24),
            idempotency_key=f"followup-{appointment_id}",
        )
    except Exception:
        logger.debug("followup_enqueue_failed")


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

    if appointment.status == AppointmentStatus.HELD:
        appointment.status = AppointmentStatus.RELEASED
        await log_event(
            session,
            participant_id=participant_id,
            event_type="slot_released",
            appointment_id=appointment_id,
            idempotency_key=payload.get("idempotency_key"),
            provenance=Provenance.SYSTEM,
            channel=Channel.SYSTEM,
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
    channel = payload.get("channel", Channel.SMS)

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
        provenance=Provenance.SYSTEM,
        channel=channel,
    )

    return {"sent": True, "channel": channel}


async def _handle_adversarial_recheck(
    session: AsyncSession,
    payload: dict,
) -> dict:
    """Run adversarial rescreen for a scheduled recheck task.

    Imports run_adversarial_rescreen lazily to avoid circular
    dependency at module load time.

    Args:
        session: Active database session.
        payload: Must contain participant_id, trial_id.

    Returns:
        Dict with rescreen result.
    """
    from src.agents.adversarial import run_adversarial_rescreen

    participant_id = uuid.UUID(payload["participant_id"])
    trial_id = payload["trial_id"]
    result = await run_adversarial_rescreen(
        session, participant_id, trial_id,
    )
    return dict(result)


_SKIP_RIDE_STATUSES = {RideStatus.CANCELLED, RideStatus.FAILED}


async def _handle_transport_reconfirm(
    session: AsyncSession,
    payload: dict,
) -> dict:
    """Reconfirm a transport ride at T-24h or T-2h.

    Loads the ride and logs a reconfirmation event unless
    the ride has been cancelled or failed.

    Args:
        session: Active database session.
        payload: Must contain ride_id, participant_id.

    Returns:
        Dict with ride_id and processing result.
    """
    ride_id = uuid.UUID(payload["ride_id"])
    participant_id = uuid.UUID(payload["participant_id"])

    ride = await get_ride(session, ride_id)
    if ride is None:
        return {"ride_id": str(ride_id), "status": "not_found"}

    if ride.status in _SKIP_RIDE_STATUSES:
        return _skipped_result(ride_id)

    await _log_reconfirm_event(session, participant_id, ride_id, payload)
    return {"ride_id": str(ride_id)}


def _skipped_result(ride_id: uuid.UUID) -> dict:
    """Build a skip result for cancelled/failed rides.

    Args:
        ride_id: Ride UUID.

    Returns:
        Dict indicating the reconfirmation was skipped.
    """
    return {
        "ride_id": str(ride_id),
        "skipped": True,
        "reason": "ride_cancelled_or_failed",
    }


async def _log_reconfirm_event(
    session: AsyncSession,
    participant_id: uuid.UUID,
    ride_id: uuid.UUID,
    payload: dict,
) -> None:
    """Log a transport reconfirmation event.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        ride_id: Ride UUID.
        payload: Task payload with idempotency_key.
    """
    await log_event(
        session,
        participant_id=participant_id,
        event_type="transport_reconfirm_sent",
        idempotency_key=payload.get("idempotency_key"),
        payload={"ride_id": str(ride_id)},
        provenance=Provenance.SYSTEM,
        channel=Channel.SMS,
    )


async def _handle_outreach_retry(
    session: AsyncSession,
    payload: dict,
) -> dict:
    """Process a deferred outreach retry attempt.

    Routes to voice (initiate_outbound_call) or SMS (render template)
    based on channel, then schedules the next cadence step.

    Args:
        session: Active database session.
        payload: Must contain participant_id, trial_id, channel,
            attempt_number.

    Returns:
        Dict with attempt number and processing status.
    """
    participant_id = uuid.UUID(payload["participant_id"])
    trial_id = payload["trial_id"]
    channel = payload.get("channel", "voice")
    attempt_number = payload.get("attempt_number", 0)

    if channel == "voice":
        await _execute_voice_retry(session, participant_id, trial_id)
    else:
        await _execute_sms_retry(session, participant_id, payload)

    await _schedule_following_attempt(
        session, participant_id, trial_id, attempt_number,
    )
    return {"attempt": attempt_number}


async def _execute_voice_retry(
    session: AsyncSession,
    participant_id: uuid.UUID,
    trial_id: str,
) -> None:
    """Execute a voice outreach retry via initiate_outbound_call.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        trial_id: Trial string identifier.
    """
    from src.agents.outreach import initiate_outbound_call

    await initiate_outbound_call(session, participant_id, trial_id)


async def _execute_sms_retry(
    session: AsyncSession,
    participant_id: uuid.UUID,
    payload: dict,
) -> None:
    """Execute an SMS outreach retry by rendering outreach_nudge.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        payload: Task payload with idempotency_key.
    """
    from src.shared.comms import render_template

    render_template("outreach_nudge")
    await log_event(
        session,
        participant_id=participant_id,
        event_type="outreach_sms_sent",
        idempotency_key=payload.get("idempotency_key"),
        payload={"template_id": "outreach_nudge"},
        provenance=Provenance.SYSTEM,
        channel=Channel.SMS,
    )


async def _schedule_following_attempt(
    session: AsyncSession,
    participant_id: uuid.UUID,
    trial_id: str,
    attempt_number: int,
) -> None:
    """Schedule the next outreach attempt after the current one.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        trial_id: Trial string identifier.
        attempt_number: Current (just-completed) attempt number.
    """
    from src.agents.outreach import schedule_next_outreach

    next_attempt = attempt_number + 1
    await schedule_next_outreach(
        session=session,
        participant_id=participant_id,
        trial_id=trial_id,
        current_attempt=next_attempt,
    )


_NO_SHOW_STATUSES = {AppointmentStatus.BOOKED, AppointmentStatus.CONFIRMED}


async def _handle_no_show_rescue(
    session: AsyncSession,
    payload: dict,
) -> dict:
    """Handle no-show detection and create handoff ticket.

    Checks if appointment is still BOOKED or CONFIRMED and
    marks it NO_SHOW with a coordinator callback ticket.

    Args:
        session: Active database session.
        payload: Must contain participant_id, appointment_id.

    Returns:
        Dict with no_show or already_completed status.
    """
    appointment_id = uuid.UUID(payload["appointment_id"])
    participant_id = uuid.UUID(payload["participant_id"])

    appointment = await _load_appointment(session, appointment_id)
    if appointment is None:
        return {"status": "not_found"}

    if appointment.status not in _NO_SHOW_STATUSES:
        return {"status": "already_completed"}

    appointment.status = AppointmentStatus.NO_SHOW
    await _log_no_show_event(session, participant_id, appointment_id, payload)
    await _create_no_show_handoff(session, participant_id, appointment)
    return {"status": "no_show"}


async def _load_appointment(
    session: AsyncSession,
    appointment_id: uuid.UUID,
) -> Appointment | None:
    """Load an appointment by ID.

    Args:
        session: Active database session.
        appointment_id: Appointment UUID.

    Returns:
        Appointment model or None if not found.
    """
    result = await session.execute(
        select(Appointment).where(
            Appointment.appointment_id == appointment_id,
        )
    )
    return result.scalar_one_or_none()


async def _log_no_show_event(
    session: AsyncSession,
    participant_id: uuid.UUID,
    appointment_id: uuid.UUID,
    payload: dict,
) -> None:
    """Log a no-show event for the appointment.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        appointment_id: Appointment UUID.
        payload: Task payload with idempotency_key.
    """
    await log_event(
        session,
        participant_id=participant_id,
        event_type="no_show_detected",
        appointment_id=appointment_id,
        idempotency_key=payload.get("idempotency_key"),
        provenance=Provenance.SYSTEM,
        channel=Channel.SYSTEM,
    )


async def _create_no_show_handoff(
    session: AsyncSession,
    participant_id: uuid.UUID,
    appointment: Appointment,
) -> None:
    """Create a callback handoff ticket for a no-show.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        appointment: Appointment model with trial_id.
    """
    await create_handoff(
        session,
        participant_id=participant_id,
        reason=HandoffReason.NO_SHOW,
        severity=HandoffSeverity.CALLBACK_TICKET,
        summary=f"No-show for appointment {appointment.appointment_id}",
        trial_id=appointment.trial_id,
    )


TASK_HANDLERS = {
    "confirmation_check": _handle_confirmation_check,
    "slot_release": _handle_slot_release,
    "appointment_reminder": _handle_reminder,
    "visit_reminder": _handle_reminder,
    "adversarial_recheck": _handle_adversarial_recheck,
    "transport_reconfirm_24h": _handle_transport_reconfirm,
    "transport_reconfirm_2h": _handle_transport_reconfirm,
    "outreach_retry": _handle_outreach_retry,
    "prep_instructions": _handle_reminder,
    "confirmation_prompt": _handle_reminder,
    "day_of_checkin": _handle_reminder,
    "no_show_rescue": _handle_no_show_rescue,
}
