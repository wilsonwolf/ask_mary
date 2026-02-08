"""Operational database CRUD operations for Cloud SQL Postgres."""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import (
    Appointment,
    Conversation,
    HandoffQueue,
    Participant,
    ParticipantTrial,
    Ride,
)
from src.shared.identity import generate_mary_id


async def create_participant(
    session: AsyncSession,
    *,
    first_name: str,
    last_name: str,
    date_of_birth: date,
    phone: str,
    pepper: str,
    agency_id: str | None = None,
    language: str = "en",
) -> Participant:
    """Create a new participant with deterministic mary_id.

    Args:
        session: Active database session.
        first_name: Participant first name.
        last_name: Participant last name.
        date_of_birth: Date of birth.
        phone: Phone number.
        pepper: MARY_ID_PEPPER for HMAC hashing.
        agency_id: Optional agency identifier.
        language: Preferred language code.

    Returns:
        Created Participant record.
    """
    mary_id = generate_mary_id(first_name, last_name, date_of_birth, phone, pepper)
    participant = Participant(
        participant_id=uuid.uuid4(),
        mary_id=mary_id,
        agency_id=agency_id,
        first_name=first_name,
        last_name=last_name,
        date_of_birth=date_of_birth,
        phone=phone,
        language=language,
        identity_status="unverified",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(participant)
    await session.flush()
    return participant


async def get_participant_by_mary_id(
    session: AsyncSession,
    mary_id: str,
) -> Participant | None:
    """Look up a participant by their deterministic identifier.

    Args:
        session: Active database session.
        mary_id: HMAC-SHA256 participant identifier.

    Returns:
        Participant if found, else None.
    """
    result = await session.execute(
        select(Participant).where(Participant.mary_id == mary_id)
    )
    return result.scalar_one_or_none()


async def get_participant_by_id(
    session: AsyncSession,
    participant_id: uuid.UUID,
) -> Participant | None:
    """Look up a participant by UUID.

    Args:
        session: Active database session.
        participant_id: Participant UUID.

    Returns:
        Participant if found, else None.
    """
    result = await session.execute(
        select(Participant).where(Participant.participant_id == participant_id)
    )
    return result.scalar_one_or_none()


async def enroll_in_trial(
    session: AsyncSession,
    *,
    participant_id: uuid.UUID,
    trial_id: str,
) -> ParticipantTrial:
    """Enroll a participant in a trial.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        trial_id: Trial identifier.

    Returns:
        Created ParticipantTrial record.
    """
    pt = ParticipantTrial(
        participant_trial_id=uuid.uuid4(),
        participant_id=participant_id,
        trial_id=trial_id,
        pipeline_status="new",
        enrollment_status="screening",
        eligibility_status="pending",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(pt)
    await session.flush()
    return pt


async def create_appointment(
    session: AsyncSession,
    *,
    participant_id: uuid.UUID,
    trial_id: str,
    visit_type: str,
    scheduled_at: datetime,
    site_name: str | None = None,
    site_address: str | None = None,
    estimated_duration_min: int | None = None,
) -> Appointment:
    """Create a new appointment.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        trial_id: Trial identifier.
        visit_type: Type of visit (screening, baseline, follow_up).
        scheduled_at: Appointment datetime (UTC).
        site_name: Name of the trial site.
        site_address: Address of the trial site.
        estimated_duration_min: Expected duration in minutes.

    Returns:
        Created Appointment record.
    """
    now = datetime.now(timezone.utc)
    appointment = Appointment(
        appointment_id=uuid.uuid4(),
        participant_id=participant_id,
        trial_id=trial_id,
        visit_type=visit_type,
        scheduled_at=scheduled_at,
        site_name=site_name,
        site_address=site_address,
        estimated_duration_min=estimated_duration_min,
        status="booked",
        created_at=now,
        updated_at=now,
    )
    session.add(appointment)
    await session.flush()
    return appointment


async def create_handoff(
    session: AsyncSession,
    *,
    participant_id: uuid.UUID,
    reason: str,
    severity: str,
    summary: str | None = None,
    conversation_id: uuid.UUID | None = None,
    trial_id: str | None = None,
    coordinator_phone: str | None = None,
    callback_number: str | None = None,
    due_at: datetime | None = None,
) -> HandoffQueue:
    """Create a handoff ticket for human coordinators.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        reason: Handoff reason code.
        severity: HANDOFF_NOW, CALLBACK_TICKET, or STOP_CONTACT.
        summary: AI-generated situation summary.
        conversation_id: Related conversation if applicable.
        trial_id: Related trial if applicable.
        coordinator_phone: Phone for warm transfer.
        callback_number: Participant callback number.
        due_at: SLA deadline.

    Returns:
        Created HandoffQueue record.
    """
    handoff = HandoffQueue(
        handoff_id=uuid.uuid4(),
        participant_id=participant_id,
        conversation_id=conversation_id,
        trial_id=trial_id,
        reason=reason,
        severity=severity,
        status="open",
        summary=summary,
        coordinator_phone=coordinator_phone,
        callback_number=callback_number,
        due_at=due_at,
        created_at=datetime.now(timezone.utc),
    )
    session.add(handoff)
    await session.flush()
    return handoff


async def create_ride(
    session: AsyncSession,
    *,
    appointment_id: uuid.UUID,
    participant_id: uuid.UUID,
    pickup_address: str,
    dropoff_address: str,
    scheduled_pickup_at: datetime,
) -> Ride:
    """Create a transport ride booking.

    Args:
        session: Active database session.
        appointment_id: Related appointment UUID.
        participant_id: Participant UUID.
        pickup_address: Pickup location.
        dropoff_address: Dropoff location.
        scheduled_pickup_at: Scheduled pickup time (UTC).

    Returns:
        Created Ride record.
    """
    now = datetime.now(timezone.utc)
    ride = Ride(
        ride_id=uuid.uuid4(),
        appointment_id=appointment_id,
        participant_id=participant_id,
        pickup_address=pickup_address,
        dropoff_address=dropoff_address,
        scheduled_pickup_at=scheduled_pickup_at,
        status="pending",
        created_at=now,
        updated_at=now,
    )
    session.add(ride)
    await session.flush()
    return ride


async def create_conversation(
    session: AsyncSession,
    *,
    participant_id: uuid.UUID,
    channel: str,
    direction: str,
    agent_name: str | None = None,
    trial_id: str | None = None,
) -> Conversation:
    """Create a conversation record.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        channel: Communication channel (voice, sms, whatsapp).
        direction: Inbound or outbound.
        agent_name: Agent handling the conversation.
        trial_id: Related trial if applicable.

    Returns:
        Created Conversation record.
    """
    conversation = Conversation(
        conversation_id=uuid.uuid4(),
        participant_id=participant_id,
        channel=channel,
        direction=direction,
        agent_name=agent_name,
        trial_id=trial_id,
        status="active",
        started_at=datetime.now(timezone.utc),
    )
    session.add(conversation)
    await session.flush()
    return conversation
