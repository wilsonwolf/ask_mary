"""Append-only event logging with idempotency key enforcement."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Event


async def log_event(
    session: AsyncSession,
    *,
    participant_id: uuid.UUID,
    event_type: str,
    idempotency_key: str | None = None,
    appointment_id: uuid.UUID | None = None,
    conversation_id: uuid.UUID | None = None,
    trial_id: str | None = None,
    payload: dict | None = None,
    provenance: str | None = None,
    channel: str | None = None,
) -> Event | None:
    """Log an event to the append-only events table.

    If an idempotency_key is provided and already exists, the event is
    silently skipped (returns None). This prevents duplicate outbound
    actions caused by retries or Cloud Tasks redelivery.

    Args:
        session: Active database session.
        participant_id: Participant this event belongs to.
        event_type: Type of event (e.g. "slot_booked", "consent_captured").
        idempotency_key: Unique key to prevent duplicate events.
        appointment_id: Related appointment if applicable.
        conversation_id: Related conversation if applicable.
        trial_id: Related trial if applicable.
        payload: Event-specific data.
        provenance: Data source (patient_stated, ehr, coordinator, system).
        channel: Communication channel (voice, sms, whatsapp, system).

    Returns:
        The created Event, or None if deduplicated.
    """
    if idempotency_key:
        existing = await session.execute(
            select(Event).where(Event.idempotency_key == idempotency_key)
        )
        if existing.scalar_one_or_none() is not None:
            return None

    event = Event(
        event_id=uuid.uuid4(),
        participant_id=participant_id,
        appointment_id=appointment_id,
        conversation_id=conversation_id,
        trial_id=trial_id,
        event_type=event_type,
        payload=payload or {},
        provenance=provenance,
        idempotency_key=idempotency_key,
        channel=channel,
        created_at=datetime.now(timezone.utc),
    )
    session.add(event)
    await session.flush()
    return event
