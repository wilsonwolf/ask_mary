"""Pydantic response models for agent function return types.

Each model defines the typed contract for an agent helper function,
replacing raw dict returns with validated Pydantic models.

All models support dict-style access (result["key"] and "key" in result)
for backward compatibility with existing safety tests.
"""

from collections.abc import Iterator
from typing import Any

from pydantic import BaseModel

from src.shared.types import (
    AdversarialCheckStatus,
    Channel,
    EligibilityStatus,
    HandoffReason,
    HandoffSeverity,
)


class AgentResult(BaseModel):
    """Base model with dict-compatible access for backward compatibility.

    Supports: result["key"], "key" in result, result.get("key"),
    {**result}, and dict(result) — so webhook handlers and safety
    tests work identically whether they receive a model or a dict.
    """

    def __getitem__(self, key: str) -> Any:
        """Support dict-style subscript access.

        Args:
            key: Field name to retrieve.

        Returns:
            Field value.

        Raises:
            AttributeError: If key is not a valid field name.
        """
        return getattr(self, key)

    def __contains__(self, key: str) -> bool:
        """Support 'key in result' membership test.

        Args:
            key: Field name to check.

        Returns:
            True if key is a model field with a non-None value.
        """
        if key not in type(self).model_fields:
            return False
        return getattr(self, key) is not None

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a field value by name with an optional default.

        Args:
            key: Field name to look up.
            default: Value to return if key is not a model field.

        Returns:
            Field value if key exists, otherwise default.
        """
        if key in type(self).model_fields:
            return getattr(self, key)
        return default

    def keys(self) -> list[str]:
        """Return all field names for dict unpacking support.

        Returns:
            List of model field name strings.
        """
        return list(type(self).model_fields.keys())

    def __iter__(self) -> Iterator[str]:  # type: ignore[override]
        """Iterate over field names for dict() and {**} unpacking."""
        return iter(type(self).model_fields.keys())


class IdentityVerificationResult(AgentResult):
    """Result of participant identity verification."""

    verified: bool
    marked: bool = False
    error: str | None = None
    reason: str | None = None
    handoff_required: bool = False
    attempts: int = 0


class DuplicateDetectionResult(AgentResult):
    """Result of duplicate participant detection."""

    is_duplicate: bool
    duplicate_ids: list[str] = []
    error: str | None = None


class ScreeningCriteriaResult(AgentResult):
    """Result of fetching screening criteria for a trial."""

    inclusion: dict[str, Any] = {}
    exclusion: dict[str, Any] = {}
    trial_name: str = ""
    error: str | None = None


class HardExcludeResult(AgentResult):
    """Result of hard exclusion check."""

    excluded: bool
    matched_criteria: list[str] = []
    reason: str = ""
    error: str | None = None


class EligibilityResult(AgentResult):
    """Result of eligibility determination."""

    eligible: bool
    status: EligibilityStatus
    reason: str
    handoff_required: bool = False


class ScreeningResponseResult(AgentResult):
    """Result of recording a screening response."""

    recorded: bool
    error: str | None = None


class GeoEligibilityResult(AgentResult):
    """Result of geographic eligibility check."""

    eligible: bool
    distance_km: float | None = None
    max_km: float | None = None
    reason: str = ""


class SlotAvailabilityResult(AgentResult):
    """Result of available appointment slot search."""

    available: bool
    slots: list[dict[str, Any]] = []
    error: str | None = None


class SlotHoldResult(AgentResult):
    """Result of holding an appointment slot."""

    held: bool
    appointment_id: str | None = None
    error: str | None = None


class AppointmentBookingResult(AgentResult):
    """Result of booking an appointment."""

    booked: bool
    appointment_id: str | None = None
    confirmation_due_at: str | None = None
    reason: str | None = None


class TeachBackResult(AgentResult):
    """Result of teach-back verification."""

    passed: bool
    handoff_required: bool = False
    attempts: int = 0
    error: str | None = None


class TransportBookingResult(AgentResult):
    """Result of transport ride booking."""

    booked: bool
    ride_id: str | None = None
    pickup_address: str = ""
    dropoff_address: str = ""
    scheduled_pickup_at: str | None = None
    error: str | None = None


class CommunicationResult(AgentResult):
    """Result of sending a communication."""

    sent: bool
    channel: Channel | None = None
    error: str | None = None


class ReminderResult(AgentResult):
    """Result of scheduling a reminder."""

    scheduled: bool
    task_id: str | None = None
    error: str | None = None


class SafetyGateResult(AgentResult):
    """Result of safety gate evaluation."""

    triggered: bool
    trigger_type: HandoffReason | None = None
    severity: HandoffSeverity | None = None
    elapsed_ms: float = 0.0


class SupervisorAuditResult(AgentResult):
    """Result of supervisor transcript audit."""

    compliant: bool
    violations: list[str] = []
    phi_detected: bool = False


class DeceptionResult(AgentResult):
    """Result of deception detection analysis."""

    deception_detected: bool
    discrepancies: list[dict[str, Any]] = []
    recheck_scheduled: bool = False


class OutreachCallResult(AgentResult):
    """Result of initiating an outreach call."""

    initiated: bool
    conversation_id: str | None = None
    error: str | None = None


class DncCheckResult(AgentResult):
    """Result of Do Not Contact check."""

    blocked: bool
    reason: str | None = None
    error: str | None = None


class StopKeywordResult(AgentResult):
    """Result of handling a STOP keyword."""

    dnc_applied: bool
    source: str | None = None


class AddressConfirmResult(AgentResult):
    """Result of confirming a pickup address."""

    confirmed: bool
    is_match: bool = False
    address_on_file: str = ""
    stated_address: str = ""


class SlotReleaseResult(AgentResult):
    """Result of releasing an expired appointment slot."""

    released: bool
    appointment_id: str | None = None
    reason: str | None = None


class CallContextResult(AgentResult):
    """Result of assembling call context."""

    context: dict[str, Any] = {}
    error: str | None = None


class VerificationPromptsResult(AgentResult):
    """Result of fetching adversarial verification prompts for a call."""

    check_status: AdversarialCheckStatus = AdversarialCheckStatus.PENDING
    prompts: list[str] = []
    discrepancies: list[dict[str, Any]] = []
    error: str | None = None


class CallOutcomeResult(AgentResult):
    """Result of recording a call outcome for retry scheduling."""

    recorded: bool = False
    outcome: str = ""
    should_retry: bool = False
    next_attempt: int | None = None
