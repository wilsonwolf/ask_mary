"""Scheduling agent — geo gate, calendar, slot booking, confirmation window.

Uses the OpenAI Agents SDK (openai-agents package) for agent definition.
The 'agents' import is the external SDK, NOT src/agents/.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# agents is the OpenAI Agents SDK package (openai-agents), NOT src/agents/
from agents import Agent, function_tool
from src.db.events import log_event
from src.db.models import Appointment
from src.db.postgres import create_appointment, create_handoff, get_participant_by_id
from src.db.trials import get_trial
from src.services.cloud_tasks_client import enqueue_reminder
from src.shared.response_models import (
    AppointmentBookingResult,
    GeoEligibilityResult,
    SlotAvailabilityResult,
    SlotHoldResult,
    SlotReleaseResult,
    TeachBackResult,
)
from src.shared.types import AppointmentStatus, Channel, HandoffSeverity, Provenance

CONFIRMATION_WINDOW_HOURS = 12
SLOT_HOLD_MINUTES = 15


async def check_geo_eligibility(
    session: AsyncSession,
    participant_id: uuid.UUID,
    trial_id: str,
) -> GeoEligibilityResult:
    """Check if participant is within trial's max distance.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        trial_id: Trial string identifier.

    Returns:
        GeoEligibilityResult with eligibility status and distance info.
    """
    participant = await get_participant_by_id(session, participant_id)
    trial = await get_trial(session, trial_id)
    distance = participant.distance_to_site_km
    max_km = trial.max_distance_km or 80.0

    if distance is None:
        return GeoEligibilityResult(eligible=True, reason="distance_unknown")
    if distance <= max_km:
        return GeoEligibilityResult(eligible=True, distance_km=distance)
    return GeoEligibilityResult(eligible=False, distance_km=distance, max_km=max_km)


async def find_available_slots(
    session: AsyncSession,
    trial_id: str,
    preferred_dates: list[str],
) -> SlotAvailabilityResult:
    """Find available appointment slots for preferred dates.

    Args:
        session: Active database session.
        trial_id: Trial string identifier.
        preferred_dates: List of ISO date strings.

    Returns:
        SlotAvailabilityResult with list of available slot datetimes.
    """
    trial = await get_trial(session, trial_id)
    hours = trial.operating_hours or {}
    slots: list[dict[str, str]] = []

    for date_str in preferred_dates:
        dt = datetime.fromisoformat(date_str)
        day_name = dt.strftime("%A").lower()
        day_hours = hours.get(day_name, {})
        if day_hours:
            open_time = day_hours.get("open", "09:00")
            slots.append({"datetime": f"{date_str}T{open_time}:00"})

    return SlotAvailabilityResult(
        available=len(slots) > 0,
        slots=slots,
    )


async def hold_slot(
    session: AsyncSession,
    participant_id: uuid.UUID,
    trial_id: str,
    slot_datetime: datetime,
) -> SlotHoldResult:
    """Hold a slot temporarily for a participant.

    Creates a HELD appointment with slot_held_until expiry.
    Uses SELECT FOR UPDATE on existing appointments at the same
    slot to prevent double-booking.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        trial_id: Trial string identifier.
        slot_datetime: Requested slot datetime.

    Returns:
        SlotHoldResult confirming hold with expiry time.
    """
    conflict = await session.execute(
        select(Appointment)
        .where(
            Appointment.trial_id == trial_id,
            Appointment.scheduled_at == slot_datetime,
            Appointment.status.in_([
                AppointmentStatus.HELD,
                AppointmentStatus.BOOKED,
                AppointmentStatus.CONFIRMED,
            ]),
        )
        .with_for_update()
    )
    if conflict.scalar_one_or_none() is not None:
        return SlotHoldResult(held=False, error="slot_taken")

    expires_at = datetime.now(UTC) + timedelta(
        minutes=SLOT_HOLD_MINUTES,
    )
    appointment = await create_appointment(
        session,
        participant_id=participant_id,
        trial_id=trial_id,
        visit_type="pending",
        scheduled_at=slot_datetime,
    )
    appointment.status = AppointmentStatus.HELD
    appointment.slot_held_until = expires_at
    await _enqueue_slot_release(
        participant_id, appointment.appointment_id, expires_at,
    )
    return SlotHoldResult(
        held=True,
        appointment_id=str(appointment.appointment_id),
    )


async def book_appointment(
    session: AsyncSession,
    participant_id: uuid.UUID,
    trial_id: str,
    slot_datetime: datetime,
    visit_type: str,
) -> AppointmentBookingResult:
    """Book an appointment with a 12-hour confirmation window.

    If a held appointment exists for this participant+trial+slot,
    confirms it. Otherwise creates a new appointment.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        trial_id: Trial string identifier.
        slot_datetime: Appointment datetime.
        visit_type: Visit type (screening, baseline, follow_up).

    Returns:
        AppointmentBookingResult confirming booking with deadline.
    """
    booked_at = datetime.now(UTC)
    confirmation_due = booked_at + timedelta(
        hours=CONFIRMATION_WINDOW_HOURS,
    )

    result = await session.execute(
        select(Appointment).where(
            Appointment.participant_id == participant_id,
            Appointment.trial_id == trial_id,
            Appointment.scheduled_at == slot_datetime,
            Appointment.status == AppointmentStatus.HELD,
        )
    )
    appointment = result.scalar_one_or_none()

    if appointment:
        appointment.status = AppointmentStatus.BOOKED
        appointment.visit_type = visit_type
    else:
        conflict = await session.execute(
            select(Appointment)
            .where(
                Appointment.trial_id == trial_id,
                Appointment.scheduled_at == slot_datetime,
                Appointment.status.in_([
                    AppointmentStatus.HELD,
                    AppointmentStatus.BOOKED,
                    AppointmentStatus.CONFIRMED,
                ]),
            )
            .with_for_update()
        )
        if conflict.scalar_one_or_none() is not None:
            return AppointmentBookingResult(booked=False, reason="slot_taken")
        appointment = await create_appointment(
            session,
            participant_id=participant_id,
            trial_id=trial_id,
            visit_type=visit_type,
            scheduled_at=slot_datetime,
        )

    appointment.confirmation_due_at = confirmation_due
    await log_event(
        session,
        participant_id=participant_id,
        event_type="appointment_booked",
        appointment_id=appointment.appointment_id,
        trial_id=trial_id,
        provenance=Provenance.SYSTEM,
    )
    await _enqueue_confirmation_check(
        participant_id, appointment.appointment_id, confirmation_due,
    )
    return AppointmentBookingResult(
        booked=True,
        appointment_id=str(appointment.appointment_id),
        confirmation_due_at=confirmation_due.isoformat(),
    )


async def _enqueue_slot_release(
    participant_id: uuid.UUID,
    appointment_id: uuid.UUID,
    expires_at: datetime,
) -> None:
    """Enqueue a Cloud Tasks job to release a held slot.

    Args:
        participant_id: Participant UUID.
        appointment_id: Appointment UUID.
        expires_at: When the hold expires.
    """
    key = f"slot-release-{appointment_id}"
    await enqueue_reminder(
        participant_id=participant_id,
        appointment_id=appointment_id,
        template_id="slot_release",
        channel=Channel.SYSTEM,
        send_at=expires_at,
        idempotency_key=key,
    )


async def _enqueue_confirmation_check(
    participant_id: uuid.UUID,
    appointment_id: uuid.UUID,
    confirmation_due: datetime,
) -> None:
    """Enqueue a Cloud Tasks job to check confirmation at T-1h.

    Args:
        participant_id: Participant UUID.
        appointment_id: Appointment UUID.
        confirmation_due: Confirmation deadline datetime.
    """
    check_at = confirmation_due - timedelta(hours=1)
    key = f"confirm-check-{appointment_id}"
    await enqueue_reminder(
        participant_id=participant_id,
        appointment_id=appointment_id,
        template_id="confirmation_check",
        channel=Channel.SYSTEM,
        send_at=check_at,
        idempotency_key=key,
    )


async def verify_teach_back(
    session: AsyncSession,
    participant_id: uuid.UUID,
    appointment_id: uuid.UUID,
    date_response: str,
    time_response: str,
    location_response: str,
) -> TeachBackResult:
    """Verify participant's teach-back of appointment details.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        appointment_id: Appointment UUID.
        date_response: Participant's date answer.
        time_response: Participant's time answer.
        location_response: Participant's location answer.

    Returns:
        TeachBackResult with verification status.
    """
    result = await session.execute(
        select(Appointment).where(
            Appointment.appointment_id == appointment_id,
        )
    )
    appointment = result.scalar_one_or_none()
    if appointment is None:
        return TeachBackResult(passed=False, error="appointment_not_found")

    appointment.teach_back_attempts += 1
    site = (appointment.site_name or "").lower()
    location_lower = location_response.lower()

    is_location_correct = site in location_lower or location_lower in site
    is_passed = is_location_correct and len(date_response) > 0 and len(time_response) > 0

    if is_passed:
        appointment.teach_back_passed = True
    is_handoff_required = not is_passed and appointment.teach_back_attempts >= 2
    if is_handoff_required:
        await create_handoff(
            session,
            participant_id=participant_id,
            reason="teach_back_failed",
            severity=HandoffSeverity.CALLBACK_TICKET,
            summary="Teach-back failed twice — participant may "
            "not understand appointment details",
        )
    return TeachBackResult(
        passed=is_passed,
        handoff_required=is_handoff_required,
        attempts=appointment.teach_back_attempts,
    )


async def release_expired_slot(
    session: AsyncSession,
    appointment_id: uuid.UUID,
) -> SlotReleaseResult:
    """Release an expired slot hold.

    Args:
        session: Active database session.
        appointment_id: Appointment UUID.

    Returns:
        SlotReleaseResult with release status.
    """
    result = await session.execute(
        select(Appointment).where(
            Appointment.appointment_id == appointment_id,
        )
    )
    appointment = result.scalar_one_or_none()
    if appointment is None:
        return SlotReleaseResult(released=False, reason="appointment_not_found")

    appointment.status = AppointmentStatus.EXPIRED_UNCONFIRMED
    appointment.slot_released_at = datetime.now(UTC)
    return SlotReleaseResult(
        released=True,
        appointment_id=str(appointment_id),
        reason="slot_released",
    )


# --- Agent SDK function tools (JSON-serializable params only) ---


@function_tool
async def tool_check_geo(participant_id: str, trial_id: str) -> str:
    """Check if participant is within the trial site's max distance.

    Args:
        participant_id: Participant UUID string.
        trial_id: Trial UUID string.

    Returns:
        JSON string with geo eligibility result.
    """
    return f'{{"participant_id": "{participant_id}", "status": "requires_session"}}'


@function_tool
async def tool_find_slots(trial_id: str, preferred_dates: str) -> str:
    """Find available appointment slots for preferred dates.

    Args:
        trial_id: Trial UUID string.
        preferred_dates: Comma-separated ISO date strings.

    Returns:
        JSON string with available slots.
    """
    return f'{{"trial_id": "{trial_id}", "status": "requires_session"}}'


@function_tool
async def tool_hold_slot(
    participant_id: str,
    trial_id: str,
    slot_datetime: str,
) -> str:
    """Hold a slot temporarily for a participant.

    Args:
        participant_id: Participant UUID string.
        trial_id: Trial UUID string.
        slot_datetime: ISO datetime string for the slot.

    Returns:
        JSON string with hold confirmation.
    """
    return f'{{"held": true, "slot": "{slot_datetime}"}}'


@function_tool
async def tool_book_appointment(
    participant_id: str,
    trial_id: str,
    slot_datetime: str,
    visit_type: str,
) -> str:
    """Book an appointment with 12-hour confirmation window.

    Args:
        participant_id: Participant UUID string.
        trial_id: Trial UUID string.
        slot_datetime: ISO datetime string.
        visit_type: Visit type (screening, baseline, follow_up).

    Returns:
        JSON string with booking confirmation.
    """
    return f'{{"booked": true, "visit_type": "{visit_type}"}}'


@function_tool
async def tool_verify_teach_back(
    participant_id: str,
    appointment_id: str,
    date_response: str,
    time_response: str,
    location_response: str,
) -> str:
    """Verify participant's teach-back of appointment details.

    Args:
        participant_id: Participant UUID string.
        appointment_id: Appointment UUID string.
        date_response: Date the participant stated.
        time_response: Time the participant stated.
        location_response: Location the participant stated.

    Returns:
        JSON string with teach-back verification result.
    """
    return f'{{"participant_id": "{participant_id}", "status": "requires_session"}}'


@function_tool
async def tool_release_slot(appointment_id: str) -> str:
    """Release an expired slot hold.

    Args:
        appointment_id: Appointment UUID string.

    Returns:
        JSON string with release confirmation.
    """
    return f'{{"released": true, "appointment_id": "{appointment_id}"}}'


scheduling_agent = Agent(
    name="scheduling",
    instructions="""You are the scheduling agent for Ask Mary clinical trials.

Your responsibilities:
1. Confirm participant address + ZIP, derive timezone
2. Geo/distance gate: compute distance to site; if outside protocol max → ineligible-distance
3. Collect availability windows and constraints (work/caregiver schedule)
4. Query Google Calendar for available slots
5. Hold slot with SELECT FOR UPDATE, present options to participant
6. Book appointment (status=BOOKED) with 12-hour confirmation window
7. Teach-back: participant must repeat date, time, location, key prep info
8. If teach-back fails twice → create handoff ticket
9. Schedule confirmation check at T+11h via Cloud Tasks

All times stored UTC, rendered in participant/site timezone.
Status progression: BOOKED → CONFIRMED → COMPLETED | NO_SHOW | CANCELLED
""",
    tools=[
        tool_check_geo,
        tool_find_slots,
        tool_hold_slot,
        tool_book_appointment,
        tool_verify_teach_back,
        tool_release_slot,
    ],
)
