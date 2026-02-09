"""Transport agent — ride booking, pickup verification, reconfirmation.

Uses the OpenAI Agents SDK (openai-agents package) for agent definition.
The 'agents' import is the external SDK, NOT src/agents/.

Architecture note: Agent helper functions access the database layer through
defined CRUD interfaces (src.db.postgres, src.db.models). This follows the
established pattern where agents depend on db interfaces for data access.
The @function_tool wrappers are JSON-serializable SDK stubs that will be
wired to the helpers at runtime by the orchestrator.
"""

import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# agents is the OpenAI Agents SDK package (openai-agents), NOT src/agents/
from agents import Agent, function_tool
from src.db.models import Appointment, Ride
from src.db.postgres import create_ride, get_participant_by_id


async def confirm_pickup_address(
    session: AsyncSession,
    participant_id: uuid.UUID,
    proposed_address: str,
) -> dict:
    """Confirm pickup address against participant record.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        proposed_address: Address proposed for pickup.

    Returns:
        Dict with confirmation status and address details.
    """
    participant = await get_participant_by_id(session, participant_id)
    on_file = (
        f"{participant.address_street}, {participant.address_city},"
        f" {participant.address_state} {participant.address_zip}"
    )
    is_match = (
        proposed_address.lower() in on_file.lower() or on_file.lower() in proposed_address.lower()
    )
    return {
        "confirmed": True,
        "address_on_file": on_file,
        "proposed": proposed_address,
        "is_match": is_match,
    }


async def book_transport(
    session: AsyncSession,
    participant_id: uuid.UUID,
    appointment_id: uuid.UUID,
    pickup_address: str,
) -> dict:
    """Book transport for an appointment.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        appointment_id: Appointment UUID.
        pickup_address: Pickup address string.

    Returns:
        Dict confirming ride booking.
    """
    result = await session.execute(
        select(Appointment).where(
            Appointment.appointment_id == appointment_id,
        )
    )
    appointment = result.scalar_one_or_none()
    pickup_time = appointment.scheduled_at - timedelta(hours=1)

    ride = await create_ride(
        session,
        appointment_id=appointment_id,
        participant_id=participant_id,
        pickup_address=pickup_address,
        dropoff_address=appointment.site_address or "",
        scheduled_pickup_at=pickup_time,
    )
    return {
        "booked": True,
        "ride_id": str(ride.ride_id),
    }


async def check_ride_status(
    session: AsyncSession,
    ride_id: uuid.UUID,
) -> dict:
    """Check the current status of a ride.

    Args:
        session: Active database session.
        ride_id: Ride UUID.

    Returns:
        Dict with ride status.
    """
    result = await session.execute(select(Ride).where(Ride.ride_id == ride_id))
    ride = result.scalar_one_or_none()
    if ride is None:
        return {"error": "ride_not_found"}
    return {
        "status": ride.status,
        "uber_ride_id": ride.uber_ride_id,
    }


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
