"""Shared types, enums, and constants used across the application."""

import enum


class IdentityStatus(str, enum.Enum):
    """Participant identity verification state."""

    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    WRONG_PERSON = "wrong_person"


class PipelineStatus(str, enum.Enum):
    """Per-trial pipeline progression state."""

    NEW = "new"
    OUTREACH = "outreach"
    SCREENING = "screening"
    SCHEDULING = "scheduling"
    BOOKED = "booked"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    NO_SHOW = "no_show"
    CANCELLED = "cancelled"
    UNREACHABLE = "unreachable"
    DNC = "dnc"


class EnrollmentStatus(str, enum.Enum):
    """Participant enrollment state within a trial."""

    SCREENING = "screening"
    ELIGIBLE = "eligible"
    ENROLLED = "enrolled"
    COMPLETED = "completed"
    WITHDRAWN = "withdrawn"
    INELIGIBLE = "ineligible"


class EligibilityStatus(str, enum.Enum):
    """Screening eligibility determination."""

    PENDING = "pending"
    ELIGIBLE = "eligible"
    PROVISIONAL = "provisional"
    INELIGIBLE = "ineligible"
    NEEDS_HUMAN = "needs_human"


class AppointmentStatus(str, enum.Enum):
    """Appointment lifecycle state."""

    HELD = "held"
    BOOKED = "booked"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    NO_SHOW = "no_show"
    CANCELLED = "cancelled"
    EXPIRED_UNCONFIRMED = "expired_unconfirmed"


class Channel(str, enum.Enum):
    """Communication channel."""

    VOICE = "voice"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    SYSTEM = "system"


class Direction(str, enum.Enum):
    """Conversation direction."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class ConversationStatus(str, enum.Enum):
    """Conversation lifecycle state."""

    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    TRANSFERRED = "transferred"


class HandoffSeverity(str, enum.Enum):
    """Handoff urgency level."""

    HANDOFF_NOW = "HANDOFF_NOW"
    CALLBACK_TICKET = "CALLBACK_TICKET"
    STOP_CONTACT = "STOP_CONTACT"


class HandoffPriority(str, enum.Enum):
    """Handoff queue priority."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class HandoffStatus(str, enum.Enum):
    """Handoff ticket lifecycle."""

    OPEN = "open"
    ASSIGNED = "assigned"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class HandoffReason(str, enum.Enum):
    """Reason for human handoff."""

    MEDICAL_ADVICE = "medical_advice"
    SEVERE_SYMPTOMS = "severe_symptoms"
    ADVERSE_EVENT = "adverse_event"
    CONSENT_WITHDRAWAL = "consent_withdrawal"
    ANGER_THREATS = "anger_threats"
    REPEATED_MISUNDERSTANDING = "repeated_misunderstanding"
    LANGUAGE_MISMATCH = "language_mismatch"
    GEO_INELIGIBLE = "geo_ineligible"
    UNREACHABLE = "unreachable"
    TEACH_BACK_FAILURE = "teach_back_failure"


class RideStatus(str, enum.Enum):
    """Transport ride lifecycle."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    DISPATCHED = "dispatched"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Provenance(str, enum.Enum):
    """Data source provenance for audit trail."""

    PATIENT_STATED = "patient_stated"
    EHR = "ehr"
    COORDINATOR = "coordinator"
    SYSTEM = "system"


class ContactabilityRisk(str, enum.Enum):
    """Participant reachability risk level."""

    NONE = "none"
    LOW = "low"
    HIGH = "high"


class VisitType(str, enum.Enum):
    """Clinical trial visit type."""

    SCREENING = "screening"
    BASELINE = "baseline"
    FOLLOW_UP = "follow_up"
