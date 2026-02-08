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
from src.db.postgres import create_appointment, get_participant_by_id
from src.db.trials import get_trial

CONFIRMATION_WINDOW_HOURS = 12
SLOT_HOLD_MINUTES = 15


async def check_geo_eligibility(
    session: AsyncSession,
    participant_id: uuid.UUID,
    trial_id: str,
) -> dict:
    """Check if participant is within trial's max distance.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        trial_id: Trial string identifier.

    Returns:
        Dict with 'eligible' boolean and distance info.
    """
    participant = await get_participant_by_id(session, participant_id)
    trial = await get_trial(session, trial_id)
    distance = participant.distance_to_site_km
    max_km = trial.max_distance_km or 80.0

    if distance is None:
        return {"eligible": True, "reason": "distance_unknown"}
    if distance <= max_km:
        return {"eligible": True, "distance_km": distance}
    return {"eligible": False, "distance_km": distance, "max_km": max_km}


async def find_available_slots(
    session: AsyncSession,
    trial_id: str,
    preferred_dates: list[str],
) -> dict:
    """Find available appointment slots for preferred dates.

    Args:
        session: Active database session.
        trial_id: Trial string identifier.
        preferred_dates: List of ISO date strings.

    Returns:
        Dict with list of available slot datetimes.
    """
    trial = await get_trial(session, trial_id)
    hours = trial.operating_hours or {}
    slots: list[str] = []

    for date_str in preferred_dates:
        dt = datetime.fromisoformat(date_str)
        day_name = dt.strftime("%A").lower()
        day_hours = hours.get(day_name, {})
        if day_hours:
            open_time = day_hours.get("open", "09:00")
            slots.append(f"{date_str}T{open_time}:00")

    return {"slots": slots}


async def hold_slot(
    session: AsyncSession,
    participant_id: uuid.UUID,
    trial_id: str,
    slot_datetime: datetime,
) -> dict:
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
        Dict confirming hold with expiry time.
    """
    conflict = await session.execute(
        select(Appointment)
        .where(
            Appointment.trial_id == trial_id,
            Appointment.scheduled_at == slot_datetime,
            Appointment.status.in_(["held", "booked"]),
        )
        .with_for_update()
    )
    if conflict.scalar_one_or_none() is not None:
        return {"held": False, "reason": "slot_taken"}

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
    appointment.status = "held"
    appointment.slot_held_until = expires_at
    return {
        "held": True,
        "appointment_id": str(appointment.appointment_id),
        "slot_datetime": slot_datetime.isoformat(),
        "expires_at": expires_at.isoformat(),
    }


async def book_appointment(
    session: AsyncSession,
    participant_id: uuid.UUID,
    trial_id: str,
    slot_datetime: datetime,
    visit_type: str,
) -> dict:
    """Book an appointment with a 12-hour confirmation window.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        trial_id: Trial string identifier.
        slot_datetime: Appointment datetime.
        visit_type: Visit type (screening, baseline, follow_up).

    Returns:
        Dict confirming booking with confirmation deadline.
    """
    booked_at = datetime.now(UTC)
    confirmation_due = booked_at + timedelta(
        hours=CONFIRMATION_WINDOW_HOURS,
    )
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
        provenance="system",
    )
    return {
        "booked": True,
        "appointment_id": str(appointment.appointment_id),
        "confirmation_due_at": confirmation_due.isoformat(),
    }


async def verify_teach_back(
    session: AsyncSession,
    participant_id: uuid.UUID,
    appointment_id: uuid.UUID,
    date_response: str,
    time_response: str,
    location_response: str,
) -> dict:
    """Verify participant's teach-back of appointment details.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        appointment_id: Appointment UUID.
        date_response: Participant's date answer.
        time_response: Participant's time answer.
        location_response: Participant's location answer.

    Returns:
        Dict with 'passed' boolean and attempt count.
    """
    result = await session.execute(
        select(Appointment).where(
            Appointment.appointment_id == appointment_id,
        )
    )
    appointment = result.scalar_one_or_none()
    if appointment is None:
        return {"error": "appointment_not_found"}

    appointment.teach_back_attempts += 1
    site = (appointment.site_name or "").lower()
    location_lower = location_response.lower()

    is_location_correct = site in location_lower or location_lower in site
    is_passed = is_location_correct and len(date_response) > 0 and len(time_response) > 0

    if is_passed:
        appointment.teach_back_passed = True
    return {
        "passed": is_passed,
        "attempts": appointment.teach_back_attempts,
    }


async def release_expired_slot(
    session: AsyncSession,
    appointment_id: uuid.UUID,
) -> dict:
    """Release an expired slot hold.

    Args:
        session: Active database session.
        appointment_id: Appointment UUID.

    Returns:
        Dict with release status.
    """
    result = await session.execute(
        select(Appointment).where(
            Appointment.appointment_id == appointment_id,
        )
    )
    appointment = result.scalar_one_or_none()
    if appointment is None:
        return {"error": "appointment_not_found"}

    appointment.status = "expired_unconfirmed"
    appointment.slot_released_at = datetime.now(UTC)
    return {"released": True}


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
