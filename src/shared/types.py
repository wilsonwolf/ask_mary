"""Shared types, enums, and constants used across the application."""

import enum


class IdentityStatus(enum.StrEnum):
    """Participant identity verification state."""

    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    WRONG_PERSON = "wrong_person"


class PipelineStatus(enum.StrEnum):
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
    INELIGIBLE = "ineligible"
    UNREACHABLE = "unreachable"
    DNC = "dnc"


class EnrollmentStatus(enum.StrEnum):
    """Participant enrollment state within a trial."""

    SCREENING = "screening"
    ELIGIBLE = "eligible"
    ENROLLED = "enrolled"
    COMPLETED = "completed"
    WITHDRAWN = "withdrawn"
    INELIGIBLE = "ineligible"


class EligibilityStatus(enum.StrEnum):
    """Screening eligibility determination."""

    PENDING = "pending"
    ELIGIBLE = "eligible"
    PROVISIONAL = "provisional"
    INELIGIBLE = "ineligible"
    NEEDS_HUMAN = "needs_human"


class AppointmentStatus(enum.StrEnum):
    """Appointment lifecycle state."""

    HELD = "held"
    BOOKED = "booked"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    NO_SHOW = "no_show"
    CANCELLED = "cancelled"
    EXPIRED_UNCONFIRMED = "expired_unconfirmed"
    RELEASED = "released"


class Channel(enum.StrEnum):
    """Communication channel."""

    VOICE = "voice"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    SYSTEM = "system"


class Direction(enum.StrEnum):
    """Conversation direction."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class ConversationStatus(enum.StrEnum):
    """Conversation lifecycle state."""

    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    TRANSFERRED = "transferred"


class HandoffSeverity(enum.StrEnum):
    """Handoff urgency level."""

    HANDOFF_NOW = "HANDOFF_NOW"
    CALLBACK_TICKET = "CALLBACK_TICKET"
    STOP_CONTACT = "STOP_CONTACT"


class HandoffPriority(enum.StrEnum):
    """Handoff queue priority."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class HandoffStatus(enum.StrEnum):
    """Handoff ticket lifecycle."""

    OPEN = "open"
    ASSIGNED = "assigned"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class HandoffReason(enum.StrEnum):
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
    NO_SHOW = "no_show"


class RideStatus(enum.StrEnum):
    """Transport ride lifecycle."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    DISPATCHED = "dispatched"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Provenance(enum.StrEnum):
    """Data source provenance for audit trail."""

    PATIENT_STATED = "patient_stated"
    EHR = "ehr"
    COORDINATOR = "coordinator"
    SYSTEM = "system"


class ContactabilityRisk(enum.StrEnum):
    """Participant reachability risk level."""

    NONE = "none"
    LOW = "low"
    HIGH = "high"


class VisitType(enum.StrEnum):
    """Clinical trial visit type."""

    SCREENING = "screening"
    BASELINE = "baseline"
    FOLLOW_UP = "follow_up"


class AdversarialCheckStatus(enum.StrEnum):
    """Background adversarial recheck status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class CallOutcome(enum.StrEnum):
    """Outcome of a completed outreach call."""

    COMPLETED = "completed"
    NO_ANSWER = "no_answer"
    VOICEMAIL = "voicemail"
    EARLY_HANGUP = "early_hangup"
    WRONG_PERSON = "wrong_person"
    REFUSED = "refused"
    CONSENT_DENIED = "consent_denied"
