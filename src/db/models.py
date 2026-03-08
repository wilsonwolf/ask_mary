"""SQLAlchemy ORM models for Ask Mary operational database."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from src.shared.types import (
    AppointmentStatus,
    ContactabilityRisk,
    ConversationStatus,
    EligibilityStatus,
    EnrollmentStatus,
    HandoffPriority,
    HandoffStatus,
    IdentityStatus,
    PipelineStatus,
    RideStatus,
)


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class Participant(Base):
    """Trial participant record.

    Attributes:
        participant_id: Primary key UUID.
        mary_id: HMAC-SHA256 deterministic identifier.
    """

    __tablename__ = "participants"

    participant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    mary_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    agency_id: Mapped[str | None] = mapped_column(String(100))
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    date_of_birth: Mapped[date] = mapped_column(Date)
    phone: Mapped[str] = mapped_column(String(20), index=True)
    secondary_phone: Mapped[str | None] = mapped_column(String(20))
    address_street: Mapped[str | None] = mapped_column(String(200))
    address_city: Mapped[str | None] = mapped_column(String(100))
    address_state: Mapped[str | None] = mapped_column(String(50))
    address_zip: Mapped[str | None] = mapped_column(String(10))
    timezone: Mapped[str | None] = mapped_column(String(50))
    distance_to_site_km: Mapped[float | None] = mapped_column(Float)
    preferred_channel: Mapped[str | None] = mapped_column(String(20))
    best_time_to_reach: Mapped[str | None] = mapped_column(String(50))
    language: Mapped[str | None] = mapped_column(String(10), default="en")
    identity_status: Mapped[str] = mapped_column(String(20), default=IdentityStatus.UNVERIFIED)
    dnc_flags: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    contactability: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    consent: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    caregiver: Mapped[dict | None] = mapped_column(JSONB)
    contactability_risk: Mapped[str] = mapped_column(String(10), default=ContactabilityRisk.NONE)
    outreach_attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    next_action_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_action_type: Mapped[str | None] = mapped_column(String(30))
    recheck_scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    trials: Mapped[list["ParticipantTrial"]] = relationship(back_populates="participant")
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="participant")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="participant")
    events: Mapped[list["Event"]] = relationship(back_populates="participant")
    rides: Mapped[list["Ride"]] = relationship(back_populates="participant")
    handoffs: Mapped[list["HandoffQueue"]] = relationship(back_populates="participant")


class ParticipantTrial(Base):
    """Junction table for multi-trial enrollment.

    Attributes:
        participant_trial_id: Primary key UUID.
        pipeline_status: Per-trial pipeline progression state.
    """

    __tablename__ = "participant_trials"

    participant_trial_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("participants.participant_id"), index=True
    )
    trial_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("trials.trial_id"),
        index=True,
    )
    pipeline_status: Mapped[str] = mapped_column(String(20), default=PipelineStatus.NEW)
    enrollment_status: Mapped[str] = mapped_column(String(20), default=EnrollmentStatus.SCREENING)
    eligibility_status: Mapped[str] = mapped_column(String(20), default=EligibilityStatus.PENDING)
    eligibility_confidence: Mapped[float | None] = mapped_column(Float)
    screening_responses: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    ehr_discrepancies: Mapped[dict | None] = mapped_column(JSONB)
    adversarial_recheck_done: Mapped[bool] = mapped_column(Boolean, default=False)
    adversarial_results: Mapped[dict | None] = mapped_column(JSONB)
    enrolled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (UniqueConstraint("participant_id", "trial_id", name="uq_participant_trial"),)

    participant: Mapped["Participant"] = relationship(back_populates="trials")


class Appointment(Base):
    """Scheduled trial visit appointment.

    Attributes:
        appointment_id: Primary key UUID.
        status: Appointment lifecycle state.
    """

    __tablename__ = "appointments"

    appointment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("participants.participant_id"), index=True
    )
    trial_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("trials.trial_id"),
    )
    visit_type: Mapped[str] = mapped_column(String(20))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    google_event_id: Mapped[str | None] = mapped_column(String(200), unique=True)
    status: Mapped[str] = mapped_column(String(30), default=AppointmentStatus.BOOKED)
    site_address: Mapped[str | None] = mapped_column(String(300))
    site_name: Mapped[str | None] = mapped_column(String(200))
    prep_instructions: Mapped[str | None] = mapped_column(Text)
    estimated_duration_min: Mapped[int | None] = mapped_column(Integer)
    slot_held_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmation_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    teach_back_passed: Mapped[bool | None] = mapped_column(Boolean)
    teach_back_attempts: Mapped[int] = mapped_column(Integer, default=0)
    cancellation_reason: Mapped[str | None] = mapped_column(String(200))
    no_show_reason: Mapped[str | None] = mapped_column(String(200))
    outcome_reason_code: Mapped[str | None] = mapped_column(String(50))
    slot_released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    participant: Mapped["Participant"] = relationship(back_populates="appointments")
    rides: Mapped[list["Ride"]] = relationship(back_populates="appointment")
    events: Mapped[list["Event"]] = relationship(back_populates="appointment")


class Conversation(Base):
    """Voice or text conversation record with full transcript.

    Attributes:
        conversation_id: Primary key UUID.
        audio_gcs_path: GCS object path (signed URLs generated on demand).
    """

    __tablename__ = "conversations"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("participants.participant_id"), index=True
    )
    trial_id: Mapped[str | None] = mapped_column(
        String(100),
        ForeignKey("trials.trial_id"),
    )
    channel: Mapped[str] = mapped_column(String(20))
    direction: Mapped[str] = mapped_column(String(20))
    agent_name: Mapped[str | None] = mapped_column(String(50))
    call_sid: Mapped[str | None] = mapped_column(String(100), unique=True)
    twilio_call_sid: Mapped[str | None] = mapped_column(String(100))
    audio_gcs_path: Mapped[str | None] = mapped_column(String(500))
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default=ConversationStatus.ACTIVE)
    full_transcript: Mapped[dict | None] = mapped_column(JSONB)
    summary: Mapped[dict | None] = mapped_column(JSONB)
    handoff_reason: Mapped[str | None] = mapped_column(String(100))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    participant: Mapped["Participant"] = relationship(back_populates="conversations")
    reasoning: Mapped[list["AgentReasoning"]] = relationship(back_populates="conversation")


class Event(Base):
    """Append-only event log with provenance and idempotency.

    Attributes:
        event_id: Primary key UUID.
        idempotency_key: Prevents duplicate outbound actions.
    """

    __tablename__ = "events"

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("participants.participant_id"), index=True
    )
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appointments.appointment_id")
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    trial_id: Mapped[str | None] = mapped_column(
        String(100),
        ForeignKey("trials.trial_id"),
    )
    event_type: Mapped[str] = mapped_column(String(50), index=True)
    payload: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    provenance: Mapped[str | None] = mapped_column(String(20))
    idempotency_key: Mapped[str | None] = mapped_column(String(200), unique=True)
    channel: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index(
            "ix_events_participant_type_created",
            "participant_id",
            "event_type",
            "created_at",
        ),
    )

    participant: Mapped["Participant"] = relationship(back_populates="events")
    appointment: Mapped["Appointment | None"] = relationship(back_populates="events")


class HandoffQueue(Base):
    """Structured handoff tasks for human coordinators.

    Attributes:
        handoff_id: Primary key UUID.
        severity: HANDOFF_NOW, CALLBACK_TICKET, or STOP_CONTACT.
    """

    __tablename__ = "handoff_queue"

    handoff_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("participants.participant_id"), index=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    trial_id: Mapped[str | None] = mapped_column(
        String(100),
        ForeignKey("trials.trial_id"),
    )
    reason: Mapped[str] = mapped_column(String(50))
    severity: Mapped[str] = mapped_column(String(20))
    priority: Mapped[str] = mapped_column(String(10), default=HandoffPriority.MEDIUM)
    status: Mapped[str] = mapped_column(String(20), default=HandoffStatus.OPEN)
    summary: Mapped[str | None] = mapped_column(Text)
    recommended_next_action: Mapped[str | None] = mapped_column(String(200))
    coordinator_phone: Mapped[str | None] = mapped_column(String(20))
    callback_number: Mapped[str | None] = mapped_column(String(20))
    language: Mapped[str | None] = mapped_column(String(10))
    preferred_callback_window: Mapped[str | None] = mapped_column(String(50))
    handoff_packet: Mapped[dict | None] = mapped_column(JSONB)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_to: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    participant: Mapped["Participant"] = relationship(back_populates="handoffs")


class Ride(Base):
    """Transport ride booking.

    Attributes:
        ride_id: Primary key UUID.
        uber_ride_id: External ride service identifier.
    """

    __tablename__ = "rides"

    ride_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    appointment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appointments.appointment_id"), index=True
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("participants.participant_id"), index=True
    )
    pickup_address: Mapped[str] = mapped_column(String(300))
    dropoff_address: Mapped[str] = mapped_column(String(300))
    scheduled_pickup_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    uber_ride_id: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default=RideStatus.PENDING)
    failure_reason: Mapped[str | None] = mapped_column(String(200))
    return_trip: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    appointment: Mapped["Appointment"] = relationship(back_populates="rides")
    participant: Mapped["Participant"] = relationship(back_populates="rides")


class Trial(Base):
    """Clinical trial definition.

    Attributes:
        trial_id: Primary key string (matches ParticipantTrial.trial_id).
        trial_name: Human-readable trial name.
    """

    __tablename__ = "trials"

    trial_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    trial_name: Mapped[str] = mapped_column(String(200))
    inclusion_criteria: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    exclusion_criteria: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    visit_templates: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    pi_name: Mapped[str | None] = mapped_column(String(200))
    coordinator_name: Mapped[str | None] = mapped_column(String(200))
    coordinator_phone: Mapped[str | None] = mapped_column(String(20))
    site_address: Mapped[str | None] = mapped_column(String(300))
    site_name: Mapped[str | None] = mapped_column(String(200))
    calendar_id: Mapped[str | None] = mapped_column(String(200))
    max_distance_km: Mapped[float | None] = mapped_column(Float, default=80.0)
    operating_hours: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class AgentReasoning(Base):
    """Agent internal reasoning trace — separated from conversations.

    Attributes:
        reasoning_id: Primary key UUID.
        reasoning_trace: Agent decisions and internal prompts.
    """

    __tablename__ = "agent_reasoning"

    reasoning_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.conversation_id"), index=True
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("participants.participant_id"), index=True
    )
    agent_name: Mapped[str] = mapped_column(String(50))
    reasoning_trace: Mapped[dict | None] = mapped_column(JSONB)
    tool_calls: Mapped[dict | None] = mapped_column(JSONB)
    safety_gate_log: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    conversation: Mapped["Conversation"] = relationship(back_populates="reasoning")
