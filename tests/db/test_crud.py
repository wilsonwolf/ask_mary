"""Integration tests for database CRUD operations against Cloud SQL."""

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config.settings import get_settings
from src.db.events import log_event
from src.db.models import Base
from src.db.postgres import (
    create_appointment,
    create_conversation,
    create_handoff,
    create_participant,
    create_ride,
    enroll_in_trial,
    get_participant_by_id,
    get_participant_by_mary_id,
)
from src.shared.identity import generate_mary_id

PEPPER = "test-pepper-for-crud-tests"


@pytest.fixture
async def db_session():
    """Create a test session that rolls back after each test.

    Yields:
        AsyncSession scoped to test, auto-rollback.
    """
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        session_factory = async_sessionmaker(
            bind=conn, class_=AsyncSession, expire_on_commit=False
        )
        async with session_factory() as session:
            yield session
            await session.rollback()
    await engine.dispose()


@pytest.fixture
async def sample_participant(db_session: AsyncSession):
    """Create and return a sample participant.

    Returns:
        Participant record for testing.
    """
    return await create_participant(
        db_session,
        first_name="Jane",
        last_name="Tester",
        date_of_birth=date(1985, 3, 15),
        phone="+1-555-000-1234",
        pepper=PEPPER,
        language="en",
    )


class TestCreateParticipant:
    """Participant creation with mary_id."""

    async def test_creates_with_mary_id(self, db_session: AsyncSession) -> None:
        """Participant is created with deterministic mary_id."""
        p = await create_participant(
            db_session,
            first_name="John",
            last_name="Doe",
            date_of_birth=date(1980, 6, 15),
            phone="5551234567",
            pepper=PEPPER,
        )
        expected_mary_id = generate_mary_id(
            "John", "Doe", date(1980, 6, 15), "5551234567", PEPPER
        )
        assert p.mary_id == expected_mary_id
        assert p.identity_status == "unverified"

    async def test_lookup_by_mary_id(self, db_session: AsyncSession) -> None:
        """Participant can be found by mary_id."""
        p = await create_participant(
            db_session,
            first_name="Alice",
            last_name="Smith",
            date_of_birth=date(1990, 1, 1),
            phone="5559999999",
            pepper=PEPPER,
        )
        found = await get_participant_by_mary_id(db_session, p.mary_id)
        assert found is not None
        assert found.participant_id == p.participant_id

    async def test_lookup_by_id(self, db_session: AsyncSession) -> None:
        """Participant can be found by UUID."""
        p = await create_participant(
            db_session,
            first_name="Bob",
            last_name="Jones",
            date_of_birth=date(1975, 12, 25),
            phone="5551111111",
            pepper=PEPPER,
        )
        found = await get_participant_by_id(db_session, p.participant_id)
        assert found is not None
        assert found.first_name == "Bob"

    async def test_not_found_returns_none(self, db_session: AsyncSession) -> None:
        """Missing participant returns None."""
        found = await get_participant_by_mary_id(db_session, "nonexistent")
        assert found is None


class TestEnrollInTrial:
    """Trial enrollment creates participant_trials record."""

    async def test_enroll(
        self, db_session: AsyncSession, sample_participant
    ) -> None:
        """Participant can be enrolled in a trial."""
        pt = await enroll_in_trial(
            db_session,
            participant_id=sample_participant.participant_id,
            trial_id="TRIAL-001",
        )
        assert pt.trial_id == "TRIAL-001"
        assert pt.pipeline_status == "new"
        assert pt.enrollment_status == "screening"
        assert pt.eligibility_status == "pending"


class TestEventLogging:
    """Append-only event logging with idempotency."""

    async def test_log_event(
        self, db_session: AsyncSession, sample_participant
    ) -> None:
        """Event is created with correct fields."""
        event = await log_event(
            db_session,
            participant_id=sample_participant.participant_id,
            event_type="consent_captured",
            provenance="patient_stated",
            channel="voice",
            payload={"disclosed_automation": True},
        )
        assert event is not None
        assert event.event_type == "consent_captured"

    async def test_idempotency_prevents_duplicate(
        self, db_session: AsyncSession, sample_participant
    ) -> None:
        """Duplicate idempotency key is silently skipped."""
        key = f"test-{uuid.uuid4()}"
        event1 = await log_event(
            db_session,
            participant_id=sample_participant.participant_id,
            event_type="slot_booked",
            idempotency_key=key,
        )
        event2 = await log_event(
            db_session,
            participant_id=sample_participant.participant_id,
            event_type="slot_booked",
            idempotency_key=key,
        )
        assert event1 is not None
        assert event2 is None

    async def test_different_keys_both_created(
        self, db_session: AsyncSession, sample_participant
    ) -> None:
        """Different idempotency keys create separate events."""
        event1 = await log_event(
            db_session,
            participant_id=sample_participant.participant_id,
            event_type="reminder_sent",
            idempotency_key=f"key-a-{uuid.uuid4()}",
        )
        event2 = await log_event(
            db_session,
            participant_id=sample_participant.participant_id,
            event_type="reminder_sent",
            idempotency_key=f"key-b-{uuid.uuid4()}",
        )
        assert event1 is not None
        assert event2 is not None


class TestAppointment:
    """Appointment creation."""

    async def test_create(
        self, db_session: AsyncSession, sample_participant
    ) -> None:
        """Appointment is created with booked status."""
        appt = await create_appointment(
            db_session,
            participant_id=sample_participant.participant_id,
            trial_id="TRIAL-001",
            visit_type="screening",
            scheduled_at=datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc),
            site_name="Valley Research Clinic",
        )
        assert appt.status == "booked"
        assert appt.site_name == "Valley Research Clinic"


class TestHandoff:
    """Handoff queue creation."""

    async def test_create(
        self, db_session: AsyncSession, sample_participant
    ) -> None:
        """Handoff ticket is created with open status."""
        handoff = await create_handoff(
            db_session,
            participant_id=sample_participant.participant_id,
            reason="medical_advice",
            severity="HANDOFF_NOW",
            summary="Participant asked about medication interactions",
        )
        assert handoff.status == "open"
        assert handoff.severity == "HANDOFF_NOW"


class TestRide:
    """Transport ride creation."""

    async def test_create(
        self, db_session: AsyncSession, sample_participant
    ) -> None:
        """Ride is created with pending status."""
        appt = await create_appointment(
            db_session,
            participant_id=sample_participant.participant_id,
            trial_id="TRIAL-001",
            visit_type="screening",
            scheduled_at=datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc),
        )
        ride = await create_ride(
            db_session,
            appointment_id=appt.appointment_id,
            participant_id=sample_participant.participant_id,
            pickup_address="123 Main St, San Francisco, CA 94107",
            dropoff_address="456 Research Way, Palo Alto, CA 94304",
            scheduled_pickup_at=datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc),
        )
        assert ride.status == "pending"
        assert ride.pickup_address == "123 Main St, San Francisco, CA 94107"


class TestConversation:
    """Conversation record creation."""

    async def test_create(
        self, db_session: AsyncSession, sample_participant
    ) -> None:
        """Conversation is created with active status."""
        convo = await create_conversation(
            db_session,
            participant_id=sample_participant.participant_id,
            channel="voice",
            direction="outbound",
            agent_name="outreach",
        )
        assert convo.status == "active"
        assert convo.channel == "voice"
