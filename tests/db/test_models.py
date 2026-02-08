"""Tests for SQLAlchemy ORM models."""

from src.db.models import (
    AgentReasoning,
    Appointment,
    Base,
    Conversation,
    Event,
    HandoffQueue,
    Participant,
    ParticipantTrial,
    Ride,
)


EXPECTED_TABLES = {
    "participants",
    "participant_trials",
    "appointments",
    "conversations",
    "agent_reasoning",
    "events",
    "handoff_queue",
    "rides",
}


def test_all_tables_defined() -> None:
    """All 8 operational tables are defined in metadata."""
    table_names = set(Base.metadata.tables.keys())
    assert EXPECTED_TABLES == table_names


def test_participant_table_name() -> None:
    """Participant model maps to correct table."""
    assert Participant.__tablename__ == "participants"


def test_participant_trial_table_name() -> None:
    """ParticipantTrial model maps to correct table."""
    assert ParticipantTrial.__tablename__ == "participant_trials"


def test_appointment_table_name() -> None:
    """Appointment model maps to correct table."""
    assert Appointment.__tablename__ == "appointments"


def test_conversation_table_name() -> None:
    """Conversation model maps to correct table."""
    assert Conversation.__tablename__ == "conversations"


def test_event_table_name() -> None:
    """Event model maps to correct table."""
    assert Event.__tablename__ == "events"


def test_handoff_queue_table_name() -> None:
    """HandoffQueue model maps to correct table."""
    assert HandoffQueue.__tablename__ == "handoff_queue"


def test_ride_table_name() -> None:
    """Ride model maps to correct table."""
    assert Ride.__tablename__ == "rides"


def test_agent_reasoning_table_name() -> None:
    """AgentReasoning model maps to correct table."""
    assert AgentReasoning.__tablename__ == "agent_reasoning"


def test_mary_id_is_unique() -> None:
    """mary_id column has unique constraint."""
    col = Participant.__table__.c.mary_id
    assert col.unique is True


def test_idempotency_key_is_unique() -> None:
    """Event idempotency_key has unique constraint."""
    col = Event.__table__.c.idempotency_key
    assert col.unique is True


def test_participant_trial_unique_constraint() -> None:
    """Each participant-trial pair is unique."""
    constraints = [
        c.name
        for c in ParticipantTrial.__table__.constraints
        if hasattr(c, "name") and c.name
    ]
    assert "uq_participant_trial" in constraints


def test_events_composite_index() -> None:
    """Events table has the participant+type+created composite index."""
    index_names = [idx.name for idx in Event.__table__.indexes]
    assert "ix_events_participant_type_created" in index_names


def test_conversation_audio_field_name() -> None:
    """Conversation stores GCS path not signed URL."""
    assert hasattr(Conversation, "audio_gcs_path")
    assert not hasattr(Conversation, "audio_url")
