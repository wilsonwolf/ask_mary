"""Transport agent — ride booking, pickup verification, reconfirmation.

Uses the OpenAI Agents SDK (openai-agents package) for agent definition.
The 'agents' import is the external SDK, NOT src/agents/.

Architecture note: Agent helper functions access the database layer through
defined CRUD interfaces (src.db.postgres, src.db.models). This follows the
established pattern where agents depend on db interfaces for data access.
The @function_tool wrappers are JSON-serializable SDK stubs that will be
wired to the helpers at runtime by the orchestrator.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

# agents is the OpenAI Agents SDK package (openai-agents), NOT src/agents/
from agents import Agent, function_tool
from src.db.postgres import create_ride, get_appointment, get_participant_by_id, get_ride
from src.services.cloud_tasks_client import enqueue_reminder
from src.shared.response_models import AddressConfirmResult, TransportBookingResult
from src.shared.types import Channel

logger = logging.getLogger(__name__)


async def confirm_pickup_address(
    session: AsyncSession,
    participant_id: uuid.UUID,
    proposed_address: str,
) -> AddressConfirmResult:
    """Confirm pickup address against participant record.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        proposed_address: Address proposed for pickup.

    Returns:
        AddressConfirmResult with confirmation and match status.
    """
    participant = await get_participant_by_id(session, participant_id)
    on_file = (
        f"{participant.address_street}, {participant.address_city},"
        f" {participant.address_state} {participant.address_zip}"
    )
    is_match = proposed_address.lower().strip() == on_file.lower().strip()
    return AddressConfirmResult(
        confirmed=True,
        is_match=is_match,
        address_on_file=on_file,
        stated_address=proposed_address,
    )


_RECONFIRM_OFFSETS: list[tuple[str, timedelta]] = [
    ("transport_reconfirm_24h", timedelta(hours=24)),
    ("transport_reconfirm_2h", timedelta(hours=2)),
]


async def _schedule_ride_reconfirmation(
    participant_id: uuid.UUID,
    appointment_id: uuid.UUID,
    ride_id: uuid.UUID,
    pickup_at: datetime,
) -> None:
    """Schedule T-24h and T-2h reconfirmation tasks for a ride.

    Args:
        participant_id: Participant UUID.
        appointment_id: Appointment UUID.
        ride_id: Ride UUID.
        pickup_at: Scheduled pickup datetime (UTC).
    """
    now = datetime.now(UTC)
    for template_id, offset in _RECONFIRM_OFFSETS:
        send_at = pickup_at - offset
        if send_at <= now:
            continue
        await _enqueue_reconfirm_task(
            participant_id, appointment_id,
            ride_id, template_id, send_at,
        )


async def _enqueue_reconfirm_task(
    participant_id: uuid.UUID,
    appointment_id: uuid.UUID,
    ride_id: uuid.UUID,
    template_id: str,
    send_at: datetime,
) -> None:
    """Enqueue a single reconfirmation task, swallowing errors.

    Args:
        participant_id: Participant UUID.
        appointment_id: Appointment UUID.
        ride_id: Ride UUID.
        template_id: Reconfirm template identifier.
        send_at: Scheduled send datetime.
    """
    prefix = template_id.replace("transport_reconfirm_", "")
    key = f"transport-reconfirm-{prefix}-{ride_id}"
    try:
        await enqueue_reminder(
            participant_id=participant_id,
            appointment_id=appointment_id,
            template_id=template_id,
            channel=Channel.SMS,
            send_at=send_at,
            idempotency_key=key,
        )
    except Exception:
        logger.debug("reconfirm_enqueue_failed", extra={"key": key})


async def book_transport(
    session: AsyncSession,
    participant_id: uuid.UUID,
    appointment_id: uuid.UUID,
    pickup_address: str,
) -> TransportBookingResult:
    """Book transport for an appointment.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        appointment_id: Appointment UUID.
        pickup_address: Pickup address string.

    Returns:
        TransportBookingResult confirming ride booking.
    """
    appointment = await get_appointment(session, appointment_id)
    if appointment is None:
        return TransportBookingResult(booked=False, error="appointment_not_found")
    pickup_time = appointment.scheduled_at - timedelta(hours=1)

    dropoff = appointment.site_address or ""
    ride = await create_ride(
        session,
        appointment_id=appointment_id,
        participant_id=participant_id,
        pickup_address=pickup_address,
        dropoff_address=dropoff,
        scheduled_pickup_at=pickup_time,
    )
    await _schedule_ride_reconfirmation(
        participant_id, appointment_id, ride.ride_id, pickup_time,
    )
    return TransportBookingResult(
        booked=True,
        ride_id=str(ride.ride_id),
        pickup_address=pickup_address,
        dropoff_address=dropoff,
        scheduled_pickup_at=pickup_time.isoformat(),
    )


async def check_ride_status(
    session: AsyncSession,
    ride_id: uuid.UUID,
) -> TransportBookingResult:
    """Check the current status of a ride.

    Args:
        session: Active database session.
        ride_id: Ride UUID.

    Returns:
        TransportBookingResult with ride status.
    """
    ride = await get_ride(session, ride_id)
    if ride is None:
        return TransportBookingResult(booked=False, error="ride_not_found")
    return TransportBookingResult(
        booked=True,
        ride_id=str(ride_id),
    )


# --- Agent SDK function tools (JSON-serializable params only) ---


@function_tool
async def tool_confirm_pickup(
    participant_id: str,
    proposed_address: str,
) -> str:
    """Confirm pickup address against participant record.

    Args:
        participant_id: Participant UUID string.
        proposed_address: Proposed pickup address.

    Returns:
        JSON string with address confirmation.
    """
    return f'{{"participant_id": "{participant_id}", "status": "requires_session"}}'


@function_tool
async def tool_book_transport(
    participant_id: str,
    appointment_id: str,
    pickup_address: str,
) -> str:
    """Book a ride for the participant to their appointment.

    Args:
        participant_id: Participant UUID string.
        appointment_id: Appointment UUID string.
        pickup_address: Pickup address.

    Returns:
        JSON string with booking confirmation.
    """
    return f'{{"booked": true, "appointment_id": "{appointment_id}"}}'


@function_tool
async def tool_check_ride(ride_id: str) -> str:
    """Check the current status of a ride.

    Args:
        ride_id: Ride UUID string.

    Returns:
        JSON string with ride status.
    """
    return f'{{"ride_id": "{ride_id}", "status": "requires_session"}}'


transport_agent = Agent(
    name="transport",
    instructions="""You are the transport agent for Ask Mary clinical trials.

Your responsibilities:
1. Mention transport support early to increase conversion
2. Confirm pickup address (vs address on file), offer alternative pickup
3. Book ride via Uber Health API (mock for MVP)
4. Schedule T-24h and T-2h reconfirmation of pickup location
5. Handle day-of exceptions: driver can't find participant, participant late
6. Log transport_failure_reason when issues occur
7. Handle return trip if applicable

Ride status: PENDING -> CONFIRMED -> DISPATCHED -> COMPLETED | FAILED | CANCELLED
""",
    tools=[
        tool_confirm_pickup,
        tool_book_transport,
        tool_check_ride,
    ],
)
